"""familia.py — telas da familia: consentimento, criancas, telefone (E3/E6/E9), contatos, horarios, historico, conta."""

import json

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, current_app, jsonify, abort

from ..tempo import texto_sp
from .. import ids, auditoria
from ..servicos import retencao as svc_ret, familia_telefones as svc_fam, turmas as svc_tur, grupos as svc_gru, contas, criancas as svc_cri, telefones as svc_tel, amizades as svc_ami, horarios as svc_hor, \
    historico as svc_hist, textos, gdms_fila
from ..servicos.contas import ErroUsuario
from .comum import conn, login_obrigatorio, consentimento_obrigatorio, crianca_da_familia

bp = Blueprint('familia', __name__)
DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']


def _cfg():
    return current_app.cfg


# --- Textos legais (publicos) ---

@bp.route('/termos')
def termos():
    return render_template('texto_legal.html', titulo='Termos de uso', texto=textos.texto('termos'), versao=_cfg().VERSAO_TERMOS)


@bp.route('/privacidade')
def privacidade():
    return render_template('texto_legal.html', titulo='Política de privacidade', texto=textos.texto('privacidade'),
                           versao=_cfg().VERSAO_PRIVACIDADE)


@bp.route('/contato')
def contato():
    """Canal publico de atendimento e de denuncias (ECA Digital, arts. 28 e 29; LGPD, canal do titular)."""
    return render_template('contato.html', contato=_cfg().CONTATO_EMAIL, privacidade=_cfg().PRIVACIDADE_EMAIL)


# --- Consentimento ---

@bp.route('/consentimento', methods=['GET', 'POST'])
@login_obrigatorio
def consentimento():
    pend = contas.consentimentos_pendentes(conn(), g.familia['id'], _cfg())
    if not pend:
        return redirect(url_for('familia.inicio'))
    if request.method == 'POST':
        marcados = [t for t in pend if request.form.get(f'aceito_{t}') == 'sim']
        if set(marcados) != set(pend):
            flash('É preciso marcar todos os itens para continuar.', 'danger')
        else:
            contas.registrar_consentimentos(conn(), g.familia['id'], marcados, g.ip, _cfg())
            return redirect(url_for('familia.inicio'))
    return render_template('consentimento.html', pendentes=pend,
                           textos={t: textos.texto(t) for t in pend}, versoes=textos.versoes(_cfg()))


# --- Inicio / criancas ---

@bp.route('/')
def inicio():
    """Visitante ve a pagina publica; familia logada vai para a crianca/telefone."""
    if not session.get('familia_id'):
        return render_template('landing.html')
    return _inicio_logado()


@login_obrigatorio
@consentimento_obrigatorio
def _inicio_logado():
    cs = svc_cri.listar(conn(), g.familia['id'])
    if not cs:
        return redirect(url_for('familia.crianca_nova'))
    if len(cs) == 1:
        c = cs[0]
        tel = svc_tel.atual_da_crianca(conn(), c['id'])
        if not tel or tel['estado'] not in ('registrado', 'ativo'):
            return redirect(url_for('familia.telefone', crianca_id=c['id']))
        return redirect(url_for('familia.contatos', crianca_id=c['id']))
    dados = [(c, svc_tel.atual_da_crianca(conn(), c['id'])) for c in cs]
    return render_template('criancas.html', dados=dados)


@bp.route('/crianca/nova', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def crianca_nova():
    if request.method == 'POST':
        try:
            c = svc_cri.criar(conn(), g.familia['id'], request.form.get('apelido'), _cfg())
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('crianca_nova.html', apelido=request.form.get('apelido', ''))
        flash(f'{c["apelido"]} criado. O ID é {ids.formatar_id(c["id_rede"])}.', 'success')
        return redirect(url_for('familia.telefone', crianca_id=c['id']))
    return render_template('crianca_nova.html', apelido='')


# --- Telefone (E3, E6, E9, E10) ---

@bp.route('/crianca/<int:crianca_id>/telefone', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def telefone(crianca_id):
    c = crianca_da_familia(crianca_id)
    tel = svc_tel.atual_da_crianca(conn(), c['id'])
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao == 'informar':
                tel = svc_tel.informar(conn(), c, request.form.get('mac'), request.form.get('serial'), g.ip, _cfg(),
                                       modelo=request.form.get('modelo') or None, loja=request.form.get('loja'),
                                       familia_id=g.familia['id'])
                _processar_fila_agora()
                flash('Dados do telefone recebidos. Estamos registrando na Grandstream.', 'success')
            elif acao == 'corrigir' and tel:
                tel = svc_tel.corrigir_dados(conn(), tel, request.form.get('mac'), request.form.get('serial'), g.ip, _cfg(), g.familia['id'])
                _processar_fila_agora()
                flash('Dados corrigidos.', 'success')
            elif acao == 'liguei' and tel:
                svc_tel.familia_informou_ligado(conn(), tel, g.familia['id'])
            elif acao == 'reconfigurar' and tel:
                svc_tel.reconfigurar(conn(), tel, 'familia', g.familia['id'], motivo=request.form.get('motivo') or 'familia_pediu')
                flash('Nova configuração gerada. O telefone vai aplicar na próxima checagem ou ao ser religado.', 'success')
            elif acao == 'remover' and tel:
                svc_tel.desativar(conn(), tel['id'], 'familia', g.familia['id'], motivo='familia_removeu', cfg=_cfg())
                _processar_fila_agora()   # manda a configuracao de fabrica ja, sem esperar o minuto do timer
                flash('Telefone removido. Não desligue o telefone: acompanhe abaixo até aparecer "pronto".', 'warning')
            elif acao == 'reativar':
                antigo = request.form.get('telefone_id', type=int)
                t = svc_tel.por_id(conn(), antigo) if antigo else None
                if not t or t['crianca_id'] != c['id']:
                    abort(404)
                svc_tel.reativar(conn(), t, 'familia', g.familia['id'], _cfg())
                _processar_fila_agora()
                flash('Telefone reativado. Estamos registrando de novo na Grandstream.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.telefone', crianca_id=c['id']))
    st = svc_tel.status(conn(), tel, _cfg()) if tel else None
    # anteriores: so os que ninguem mais usa (um aparelho entregue a outra familia some daqui)
    desativados = [t for t in svc_tel.listar_da_crianca(conn(), c['id'], incluir_desativados=True)
                   if t['estado'] == 'desativado' and not svc_tel.por_mac_ativo(conn(), t['mac'])]
    zer = svc_tel.zeramento(conn(), desativados[0]) if (not tel and desativados) else None
    if zer and zer['fase'] != 'andamento' and zer['minutos'] > 30:
        zer = None   # terminou ha tempo: volta a pagina normal
    return render_template('telefone.html', crianca=c, tel=tel, st=st, desativados=desativados[:3], active_tab='telefone',
                           modelos=svc_tel.MODELOS_FAMILIA, zeramento=zer, zeramento_tel=desativados[0] if zer else None)


def _processar_fila_agora():
    """Tenta cadastrar no GDMS na hora (melhor esforco); o job de 1 min cobre o resto."""
    try:
        gdms_fila.processar(conn(), _cfg())
    except Exception:
        current_app.logger.exception('gdms_fila inline falhou')


@bp.route('/crianca/<int:crianca_id>/telefone/status.json')
@login_obrigatorio
def telefone_status(crianca_id):
    c = crianca_da_familia(crianca_id)
    tel = svc_tel.atual_da_crianca(conn(), c['id'])
    if not tel:
        return jsonify({'estado': None})
    st = svc_tel.status(conn(), tel, _cfg())
    return jsonify(st)


@bp.route('/crianca/<int:crianca_id>/telefone/zeramento.json')
@login_obrigatorio
def telefone_zeramento(crianca_id):
    c = crianca_da_familia(crianca_id)
    desativados = [t for t in svc_tel.listar_da_crianca(conn(), c['id'], incluir_desativados=True) if t['estado'] == 'desativado']
    z = svc_tel.zeramento(conn(), desativados[0]) if desativados else None
    return jsonify(z or {'fase': None})


@bp.route('/crianca/<int:crianca_id>/telefone/senha-admin', methods=['POST'])
@login_obrigatorio
def telefone_senha_admin(crianca_id):
    c = crianca_da_familia(crianca_id)
    tel = svc_tel.atual_da_crianca(conn(), c['id'])
    if not tel:
        abort(404)
    senha = svc_tel.senha_admin_consultada(conn(), tel, g.familia['id'])
    flash(f'Senha de administrador do telefone: {senha}', 'info')
    return redirect(url_for('familia.telefone', crianca_id=c['id']))


# --- Contatos (amizades) ---

@bp.route('/crianca/<int:crianca_id>/contatos', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def contatos(crianca_id):
    c = crianca_da_familia(crianca_id)
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao == 'pedir':
                r = svc_ami.pedir(conn(), c, request.form.get('id_rede'), g.familia['id'], _cfg(),
                                  mensagem=request.form.get('mensagem'))
                if r is not None and r['estado'] == 'aceita':
                    flash('Vocês já tinham um pedido pendente um do outro. Amizade aceita.', 'success')
                else:
                    flash('Pedido enviado. A outra família precisa aceitar.', 'success')
            elif acao in ('aceitar', 'recusar', 'bloquear', 'remover'):
                svc_ami.responder(conn(), request.form.get('amizade_id', type=int), g.familia['id'], acao)
                flash({'aceitar': 'Amizade aceita.', 'recusar': 'Pedido recusado.', 'bloquear': 'Contato bloqueado.',
                       'remover': 'Contato removido.'}[acao], 'success')
            elif acao == 'desbloquear':
                svc_ami.desbloquear(conn(), request.form.get('amizade_id', type=int), g.familia['id'])
                flash('Desbloqueado.', 'success')
            elif acao == 'grupo_criar':
                gr = svc_gru.criar(conn(), g.familia['id'], c, request.form.get('nome'), request.form.getlist('membros'))
                codigo = [x for x in svc_gru.listar_da_crianca(conn(), c) if x['id'] == gr['id']][0]['discar']
                flash(f'Grupo "{gr["nome"]}" criado. No telefone de {c["apelido"]}, disca {codigo}#. Imprima o cartão de novo.', 'success')
                return redirect(url_for('familia.contatos', crianca_id=c['id']) + '#grupos')
            elif acao == 'grupo_sair':
                svc_gru.sair(conn(), g.familia['id'], request.form.get('grupo_id', type=int), c)
                flash(f'{c["apelido"]} saiu do grupo.', 'success')
                return redirect(url_for('familia.contatos', crianca_id=c['id']) + '#grupos')
            elif acao == 'grupo_remover':
                svc_gru.remover(conn(), g.familia['id'], request.form.get('grupo_id', type=int), c)
                flash('Grupo removido.', 'success')
                return redirect(url_for('familia.contatos', crianca_id=c['id']) + '#grupos')
        except ErroUsuario as e:
            flash(str(e), 'danger')
            # os formularios tem pagina propria: o erro volta para ela, com o que foi digitado
            if acao == 'pedir':
                return _pagina_pedir(c, {'id_rede': request.form.get('id_rede', ''), 'mensagem': request.form.get('mensagem', '')})
            if acao == 'grupo_criar':
                return _pagina_grupo_novo(c, request.form.get('nome', ''), request.form.getlist('membros'))
        return redirect(url_for('familia.contatos', crianca_id=c['id']))
    lst = svc_ami.listar(conn(), c['id'])
    return render_template('contatos.html', crianca=c, lst=lst, active_tab='contatos',
                           grupos=svc_gru.listar_da_crianca(conn(), c), amigos_grupo=svc_gru.amigos_para_grupo(conn(), c),
                           max_membros=svc_gru.MAX_MEMBROS)


def _pagina_pedir(c, valores=None):
    return render_template('contatos_pedir.html', crianca=c, active_tab='contatos', valores=valores)


def _pagina_grupo_novo(c, nome='', pre=()):
    pre = [int(x) for x in pre if str(x).isdigit()]
    return render_template('grupo_novo.html', crianca=c, active_tab='contatos', nome=nome,
                           amigos_grupo=svc_gru.amigos_para_grupo(conn(), c, pre),
                           max_grupos=svc_gru.MAX_GRUPOS_POR_CRIANCA, max_membros=svc_gru.MAX_MEMBROS,
                           max_na_chamada=_cfg().GRUPO_MAX_NA_CHAMADA)


@bp.route('/crianca/<int:crianca_id>/contatos/pedir')
@login_obrigatorio
@consentimento_obrigatorio
def contatos_pedir(crianca_id):
    """Pagina "Adicionar amigo". O envio vai para a rota contatos (acao=pedir)."""
    return _pagina_pedir(crianca_da_familia(crianca_id))


@bp.route('/crianca/<int:crianca_id>/grupos/novo')
@login_obrigatorio
@consentimento_obrigatorio
def grupo_novo(crianca_id):
    """Pagina "Criar grupo". ?turma=<id> pre-seleciona os amigos aceitos daquela turma. Envio: contatos (acao=grupo_criar)."""
    c = crianca_da_familia(crianca_id)
    pre = []
    turma_id = request.args.get('turma', type=int)
    if turma_id:
        t = svc_tur.por_id(conn(), turma_id)
        if t:
            pre = [m['crianca_id'] for m in svc_tur.visao(conn(), t, c) if m['relacao'] == 'amigo']
    return _pagina_grupo_novo(c, '', pre)


@bp.route('/crianca/<int:crianca_id>/turmas', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def turmas(crianca_id):
    c = crianca_da_familia(crianca_id)
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao == 'criar':
                t = svc_tur.criar(conn(), g.familia['id'], c, request.form.get('nome'))
                flash(f'Turma "{t["nome"]}" criada. Passe o código {svc_tur.formatar_codigo(t["codigo"])} para as outras famílias.', 'success')
                return redirect(url_for('familia.turma', crianca_id=c['id'], turma_id=t['id']))
            elif acao == 'entrar':
                t = svc_tur.entrar(conn(), g.familia['id'], c, request.form.get('codigo'))
                flash(f'Pedido enviado para a turma "{t["nome"]}". Quem administra a turma precisa aceitar.', 'success')
            elif acao == 'sair':
                svc_tur.sair(conn(), request.form.get('turma_id', type=int), c, g.familia['id'])
                flash('Saiu da turma. As amizades já aceitas continuam.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.turmas', crianca_id=c['id']))
    return render_template('turmas.html', crianca=c, turmas=svc_tur.das_criancas(conn(), c['id']), active_tab='turmas')


@bp.route('/crianca/<int:crianca_id>/turma/<int:turma_id>', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def turma(crianca_id, turma_id):
    c = crianca_da_familia(crianca_id)
    t = svc_tur.por_id(conn(), turma_id)
    minhas = {x['id'] for x in svc_tur.das_criancas(conn(), c['id'])}
    if not t or (t['id'] not in minhas and t['familia_id'] != g.familia['id']):
        abort(404)
    admin = t['familia_id'] == g.familia['id']
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao in ('aceitar', 'recusar') and admin:
                novo, pedidos = svc_tur.responder(conn(), request.form.get('membro_id', type=int), g.familia['id'], acao, _cfg())
                flash('Entrada aceita. A criança já pediu amizade aos membros da turma.' if novo == 'aceita' else 'Entrada recusada.', 'success')
            elif acao == 'pedir':
                svc_ami.pedir(conn(), c, request.form.get('id_rede'), g.familia['id'], _cfg(), mensagem=f'da turma {t["nome"]}')
                flash('Pedido enviado.', 'success')
            elif acao == 'aceitar_amizade':
                svc_ami.responder(conn(), request.form.get('amizade_id', type=int), g.familia['id'], 'aceitar')
                flash('Amizade aceita.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.turma', crianca_id=c['id'], turma_id=t['id']))
    membros = svc_tur.visao(conn(), t, c)
    return render_template('turma.html', crianca=c, turma=t, admin=admin, membros=membros,
                           codigo_fmt=svc_tur.formatar_codigo(t['codigo']), active_tab='turmas')


@bp.route('/turma/<int:turma_id>')
@login_obrigatorio
def turma_atalho(turma_id):
    """Link do e-mail: leva para a turma pela primeira crianca da familia que esta nela (ou que administra)."""
    t = svc_tur.por_id(conn(), turma_id)
    if not t:
        abort(404)
    for c in svc_cri.listar(conn(), g.familia['id']):
        if t['familia_id'] == g.familia['id'] or t['id'] in {x['id'] for x in svc_tur.das_criancas(conn(), c['id'])}:
            return redirect(url_for('familia.turma', crianca_id=c['id'], turma_id=t['id']))
    abort(404)


@bp.route('/crianca/<int:crianca_id>/cartao')
@login_obrigatorio
def cartao(crianca_id):
    c = crianca_da_familia(crianca_id)
    lst = svc_ami.listar(conn(), c['id'])
    celulares = [(t['apelido'] or f'Celular {t["posicao"]}', svc_fam.PREFIXOS[t['posicao']] + c['id_rede'])
                 for t in svc_fam.listar(conn(), g.familia['id']) if t['posicao'] in svc_fam.PREFIXOS]
    return render_template('cartao.html', crianca=c, amigos=lst['amigos'], celulares=celulares,
                           grupos=svc_gru.para_cartao(conn(), c))


# --- Horarios ---

@bp.route('/crianca/<int:crianca_id>/horarios', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def horarios(crianca_id):
    c = crianca_da_familia(crianca_id)
    if request.method == 'POST' and request.form.get('acao') in ('silenciar', 'reativar'):
        try:
            if request.form.get('acao') == 'silenciar':
                ate = svc_hor.silenciar(conn(), c['id'], request.form.get('duracao'), g.familia['id'])
                flash(f'Telefone silenciado até {texto_sp(ate, "%d/%m às %H:%M")}.', 'success')
            else:
                svc_hor.reativar(conn(), c['id'], g.familia['id'])
                flash('Telefone reativado.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.horarios', crianca_id=c['id']))
    if request.method == 'POST':
        padroes = []
        try:
            n = int(request.form.get('pattern_count', '0'))
        except ValueError:
            n = 0
        for i in range(n):
            dias = request.form.getlist(f'days_{i}')
            if not dias:
                continue
            padroes.append({'inicio': f"{request.form.get(f'start_h_{i}', '00')}:{request.form.get(f'start_m_{i}', '00')}",
                            'fim': f"{request.form.get(f'end_h_{i}', '00')}:{request.form.get(f'end_m_{i}', '00')}",
                            'dias': [int(d) for d in dias]})
        try:
            svc_hor.salvar(conn(), c['id'], padroes, g.familia['id'])
            flash('Horários salvos.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.horarios', crianca_id=c['id']))
    pats = svc_hor.agrupar(svc_hor.listar(conn(), c['id']))
    silencio = svc_hor.silencio_ativo(c)
    return render_template('horarios.html', crianca=c, patterns_json=json.dumps(pats), tem=bool(pats), active_tab='horarios',
                           silencio_ate=texto_sp(silencio, '%d/%m às %H:%M') if silencio else None, duracoes=svc_hor.DURACOES_SILENCIO)


# --- Historico ---

@bp.route('/crianca/<int:crianca_id>/historico')
@login_obrigatorio
@consentimento_obrigatorio
def historico(crianca_id):
    c = crianca_da_familia(crianca_id)
    pagina = max(1, request.args.get('page', 1, type=int))
    logs, total = svc_hist.listar(conn(), c['id_rede'], pagina)
    exts = {l['caller_ext'] for l in logs} | {l['callee_ext'] for l in logs}
    nomes = svc_hist.nomes(conn(), exts)
    nomes['100'] = 'Hora certa'
    chart = svc_hist.tempo_por_contato(conn(), c['id_rede'])
    nomes.update(svc_hist.nomes(conn(), {x['contact_ext'] for x in chart}))
    retornar = svc_hist.para_retornar(conn(), c['id_rede'])
    nomes.update(svc_hist.nomes(conn(), {x['contato'] for x in retornar}))
    return render_template('historico.html', crianca=c, logs=logs, total=total, page=pagina, retornar=retornar,
                           total_pages=max(1, (total + 99) // 100), ext_names=nomes,
                           total_duration=svc_hist.tempo_total(conn(), c['id_rede']),
                           chart_data_json=json.dumps(chart), ext_names_json=json.dumps(nomes), active_tab='historico')


# --- Conta ---

# --- Celulares da familia (9+ID e entrada pelo tronco) ---

@bp.route('/celulares', methods=['GET', 'POST'])
@login_obrigatorio
@consentimento_obrigatorio
def celulares():
    fid = g.familia['id']
    if request.method == 'POST':
        try:
            if request.form.get('acao') == 'remover':
                svc_fam.remover(conn(), fid, int(request.form.get('id', '0') or 0))
                flash('Número removido.', 'success')
            elif request.form.get('acao') == 'trocar':
                svc_fam.trocar_ordem(conn(), fid)
                flash('Ordem trocada.', 'success')
            else:
                n = svc_fam.adicionar(conn(), fid, request.form.get('numero', ''), request.form.get('apelido', ''))
                flash(f'Número {svc_fam.formatar(n)} cadastrado.', 'success')
        except ErroUsuario as e:
            flash(str(e), 'danger')
        return redirect(url_for('familia.celulares'))
    cs = svc_cri.listar(conn(), fid)
    from ..servicos import custos
    gastos = [(c, custos.gasto_crianca_mes(conn(), c['id_rede'], _cfg())) for c in cs]
    return render_template('celulares.html', numeros=svc_fam.listar(conn(), fid), criancas=cs, gastos=gastos, teto=_cfg().TETO_CRIANCA_MES,
                           maximo=svc_fam.MAX_POR_FAMILIA, formatar=svc_fam.formatar, prefixos=svc_fam.PREFIXOS,
                           numero_rede=svc_fam.formatar(_cfg().TRONCO_NUMERO) or 'o número da rede')


@bp.route('/meus-dados.json')
@login_obrigatorio
def meus_dados():
    """Portabilidade/acesso (LGPD art. 18): tudo o que a rede guarda sobre a familia, em JSON."""
    from flask import Response
    from sqlalchemy import select, text as sql
    from .. import db
    fid = g.familia['id']
    c = conn()
    fam = contas.por_id(c, fid)
    out = {'gerado_em': texto_sp(svc_ret.agora(), '%d/%m/%Y %H:%M'), 'versao': 1,
           'responsavel': {'nome': fam['nome'], 'email': fam['email'], 'criado_em': texto_sp(fam['criado_em']),
                           'verificado_em': texto_sp(fam['verificado_em']) if fam['verificado_em'] else None},
           'consentimentos': [{'tipo': r['tipo'], 'versao': r['versao'], 'quando': texto_sp(r['ts'])}
                              for r in c.execute(select(db.consentimentos).where(db.consentimentos.c.familia_id == fid)).mappings()],
           'celulares': [{'numero': t['numero'], 'apelido': t['apelido'], 'posicao': t['posicao']} for t in svc_fam.listar(c, fid)],
           'criancas': []}
    for cr in svc_cri.listar(c, fid, incluir_inativas=True):
        item = {'apelido': cr['apelido'], 'id': cr['id_rede'], 'ativa': bool(cr['ativa']), 'criado_em': texto_sp(cr['criado_em']),
                'telefones': [], 'amigos': [], 'pedidos': [], 'horarios': [], 'ligacoes': []}
        for t in svc_tel.listar_da_crianca(c, cr['id'], incluir_desativados=True):
            item['telefones'].append({'mac': t['mac'], 'serial': t['serial'], 'modelo': t['modelo'], 'estado': t['estado'],
                                      'informado_em': texto_sp(t['informado_em']), 'ultimo_sip_ip': t['ultimo_sip_ip']})
        if cr['ativa']:
            lst = svc_ami.listar(c, cr['id'])
            item['amigos'] = [{'apelido': a['apelido'], 'id': a['id_rede']} for a in lst['amigos']]
            item['pedidos'] = [{'apelido': a['apelido'], 'id': a['id_rede'], 'sentido': k}
                               for k in ('recebidos', 'enviados') for a in lst[k]]
            item['horarios'] = [dict(r) for r in svc_hor.agrupar(svc_hor.listar(c, cr['id']))]
        rows = c.execute(sql("SELECT timestamp, caller_ext, callee_ext, status, duration_seconds, block_reason FROM call_logs "
                             "WHERE caller_ext = :e OR callee_ext = :e ORDER BY timestamp DESC"), {'e': cr['id_rede']}).mappings().all()
        item['ligacoes'] = [dict(r) for r in rows]
        out['criancas'].append(item)
    auditoria.registrar(c, 'dados_exportados', 'familia', fid, 'familia', fid)
    body = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    return Response(body, mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename="meus-dados-telefonefixo.json"'})


@bp.route('/excluir-conta', methods=['GET', 'POST'])
@login_obrigatorio
def excluir_conta():
    cs = svc_cri.listar(conn(), g.familia['id'])
    if request.method == 'POST':
        try:
            contas.excluir_conta(conn(), g.familia['id'], request.form.get('confirmacao'), g.ip, _cfg())
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('excluir_conta.html', criancas=cs)
        session.clear()
        flash('Conta excluída. Todos os dados pessoais foram removidos.', 'success')
        return redirect(url_for('auth.entrar'))
    return render_template('excluir_conta.html', criancas=cs)
