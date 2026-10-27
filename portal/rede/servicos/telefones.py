"""
telefones.py — E3 (MAC + serial), token e XML de provisionamento (E7), reconfigurar,
trocar, desativar, reativar. Estados so mudam via estados.transicionar().
"""

import itertools
import re
from datetime import timedelta

from sqlalchemy import select, insert, update, and_, func

from .. import db, auditoria, seguranca, estados, grandstream_xml, gdms_client
from ..tempo import agora, utc
from .contas import ErroUsuario
from . import criancas as svc_cri

SERIAL_RE = re.compile(r'^[A-Z0-9]{8,32}$')


# Modelos que a familia pode escolher na tela. 'grpw' = GRP2602W (Wi-Fi): mesma configuracao do GRP2601,
# muda so o passo "ligar" (sem cabo de rede, com o passo a passo do Wi-Fi no menu do aparelho).
MODELOS_FAMILIA = {'grp': 'GRP2601 (cabo de rede)', 'grpw': 'GRP2602W (Wi-Fi)'}

def por_id(conn, telefone_id):
    return conn.execute(select(db.telefones).where(db.telefones.c.id == telefone_id)).mappings().first()


def listar_da_crianca(conn, crianca_id, incluir_desativados=False):
    q = select(db.telefones).where(db.telefones.c.crianca_id == crianca_id)
    if not incluir_desativados:
        q = q.where(db.telefones.c.estado != 'desativado')
    return conn.execute(q.order_by(db.telefones.c.id.desc())).mappings().all()


def atual_da_crianca(conn, crianca_id):
    lst = listar_da_crianca(conn, crianca_id)
    return lst[0] if lst else None


def por_mac_ativo(conn, mac):
    return conn.execute(select(db.telefones).where(and_(db.telefones.c.mac == mac,
                                                       db.telefones.c.estado != 'desativado'))).mappings().first()


def normalizar_mac(mac):
    try:
        return grandstream_xml.normalizar_mac(mac)
    except ValueError:
        raise ErroUsuario('MAC inválido. São 12 letras e números, como na etiqueta, por exemplo C074AD1A2B3C.')


def normalizar_serial(sn):
    s = re.sub(r'[\s\-_.:]', '', sn or '').upper()
    if not SERIAL_RE.match(s):
        raise ErroUsuario('Número de série inválido. Copie exatamente o que está na etiqueta (S/N).')
    return s


CONFUSOES_SERIAL = {'O': '0', 'Q': '0', 'I': '1', 'L': '1'}


def variantes_serial(sn, maximo=16):
    """Outras leituras possiveis do S/N: letras que parecem digitos viram o digito (O/Q->0, I/L->1).
    So nesse sentido: a leitura errada quase sempre e tomar um 0 por O ou 1 por I, e os S/N da
    Grandstream que vimos (35103ZC1D2, 35304JXXXX) nao usam essas letras. Como letras e numeros nao
    tem posicao fixa, nao da para adivinhar: o portal tenta as variantes no device/add e o GDMS diz
    qual e a certa. A primeira variante e a mais provavel (todas as letras trocadas)."""
    posicoes = [i for i, ch in enumerate(sn) if ch in CONFUSOES_SERIAL]
    saida = []
    for n in range(len(posicoes), 0, -1):
        for combo in itertools.combinations(posicoes, n):
            chars = list(sn)
            for i in combo:
                chars[i] = CONFUSOES_SERIAL[chars[i]]
            saida.append(''.join(chars))
            if len(saida) >= maximo:
                return saida
    return saida


def token_ativo(conn, telefone_id):
    return conn.execute(select(db.prov_tokens).where(and_(db.prov_tokens.c.telefone_id == telefone_id,
                                                         db.prov_tokens.c.ativo == True))).mappings().first()  # noqa: E712


def _novo_token(conn, telefone_id):
    tok = seguranca.token_url(32)
    conn.execute(insert(db.prov_tokens).values(telefone_id=telefone_id, token=tok, ativo=True, criado_em=agora()))
    return tok


def revogar_tokens(conn, telefone_id, motivo):
    conn.execute(update(db.prov_tokens).where(and_(db.prov_tokens.c.telefone_id == telefone_id,
                                                  db.prov_tokens.c.ativo == True))  # noqa: E712
                 .values(ativo=False, revogado_em=agora(), motivo_revogacao=motivo))


def url_provisionamento(cfg, token):
    return f'{cfg.PROV_URL}/p/{token}/'


# --- E3 ---

def informar(conn, crianca, mac, serial, ip, cfg, modelo=None, loja=None, familia_id=None):
    """Familia informa MAC + serial. Cria o telefone em dados_informados, token e fila GDMS."""
    from . import gdms_fila
    familia_id = familia_id or crianca['familia_id']
    chave = f'mac:{familia_id}'
    if seguranca.excedeu(chave, cfg.LIMITE_MAC_TENTATIVAS_HORA, 3600):
        auditoria.registrar(conn, 'telefone_dados_bloqueado_rate_limit', 'familia', familia_id, 'crianca', crianca['id'])
        raise ErroUsuario('Muitas tentativas. Aguarde uma hora e tente de novo.')
    seguranca.registrar_tentativa(chave)
    try:
        mac_n = normalizar_mac(mac)
        serial_n = normalizar_serial(serial)
    except ErroUsuario as e:
        auditoria.registrar(conn, 'telefone_dados_rejeitados', 'familia', familia_id, 'crianca', crianca['id'],
                            detalhes={'motivo': str(e)})
        raise
    if not gdms_client.mac_e_grandstream(mac_n):
        auditoria.registrar(conn, 'telefone_dados_rejeitados', 'familia', familia_id, 'crianca', crianca['id'],
                            detalhes={'motivo': 'prefixo_nao_grandstream', 'prefixo': mac_n[:6]})
        raise ErroUsuario('Esse MAC não parece ser de um telefone Grandstream. Confira a etiqueta.')
    modelo = modelo or cfg.MODELO_PADRAO
    if modelo not in MODELOS_FAMILIA:
        raise ErroUsuario('Escolha o modelo do telefone.')

    # MAC ja em uso?
    existente = por_mac_ativo(conn, mac_n)
    if existente:
        dono = svc_cri.por_id(conn, existente['crianca_id'])
        if dono and dono['familia_id'] == familia_id:
            if existente['crianca_id'] == crianca['id']:
                raise ErroUsuario('Este telefone já está cadastrado para esta criança.')
            raise ErroUsuario('Este telefone já está cadastrado para outra criança da sua conta. Remova-o de lá primeiro.')
        # Outra familia: nunca sobrescrever. Abre caso e avisa.
        cid = conn.execute(insert(db.casos).values(
            tipo='mac_duplicado', gravidade='alta', telefone_id=existente['id'], crianca_id=crianca['id'],
            familia_id=familia_id, estado='aberto', criado_em=agora(),
            descricao=f'MAC {mac_n} informado pela família {familia_id} já pertence ao telefone {existente["id"]} (família {dono["familia_id"] if dono else "?"})',
            detalhes={'mac': mac_n, 'familia_nova': familia_id, 'telefone_existente': existente['id']})).inserted_primary_key[0]
        auditoria.registrar(conn, 'alerta_mac_duplicado', 'sistema', None, 'telefone', existente['id'],
                            detalhes={'mac': mac_n, 'familia_nova': familia_id, 'caso_id': cid})
        raise ErroUsuario('Este telefone já está cadastrado por outra família. Se você comprou um aparelho usado, '
                          'nossa equipe vai verificar e entrar em contato pelo seu e-mail.')

    # Telefone anterior desta crianca? vira troca
    anterior = atual_da_crianca(conn, crianca['id'])
    if anterior:
        desativar(conn, anterior['id'], 'familia', familia_id, motivo='troca_de_aparelho', cfg=cfg, evento='troca_de_aparelho')

    r = conn.execute(insert(db.telefones).values(
        crianca_id=crianca['id'], mac=mac_n, serial=serial_n, modelo=modelo, estado='dados_informados',
        admin_senha=seguranca.senha_admin_aparelho(), xml_versao=1, informado_em=agora(), loja=(loja or None)))
    tid = r.inserted_primary_key[0]
    # Estado inicial: registra a transicao None -> dados_informados no historico/auditoria
    aid = auditoria.registrar(conn, 'telefone_dados_informados', 'familia', familia_id, 'telefone', tid,
                              detalhes={'mac': mac_n, 'serial': serial_n, 'modelo': modelo, 'crianca_id': crianca['id'],
                                        'troca_de': anterior['id'] if anterior else None}, ip=ip)
    conn.execute(db.device_state_history.insert().values(ts=agora(), telefone_id=tid, de=None, para='dados_informados',
                                                         evento='dados_informados', ator_tipo='familia',
                                                         ator_id=str(familia_id), audit_id=aid))
    _novo_token(conn, tid)
    gdms_fila.enfileirar(conn, tid)
    return por_id(conn, tid)


def corrigir_dados(conn, telefone, mac, serial, ip, cfg, familia_id):
    """Familia corrige MAC/serial apos erro_dados ou conflito. Gera nova entrada na fila."""
    from . import gdms_fila
    if telefone['estado'] not in ('erro_dados', 'erro_gdms_conflito', 'sem_boot', 'dados_informados'):
        raise ErroUsuario('Este telefone não está em um estado que permita correção.')
    mac_n = normalizar_mac(mac)
    serial_n = normalizar_serial(serial)
    outro = por_mac_ativo(conn, mac_n)
    if outro and outro['id'] != telefone['id']:
        raise ErroUsuario('Este MAC já está cadastrado em outro telefone.')
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone['id'])
                 .values(mac=mac_n, serial=serial_n, informado_em=agora()))
    auditoria.registrar(conn, 'telefone_dados_corrigidos', 'familia', familia_id, 'telefone', telefone['id'],
                        detalhes={'de_mac': telefone['mac'], 'para_mac': mac_n, 'de_serial': telefone['serial'],
                                  'para_serial': serial_n}, ip=ip)
    if telefone['estado'] != 'dados_informados':
        estados.transicionar(conn, telefone['id'], 'dados_informados', 'familia', familia_id)
    gdms_fila.enfileirar(conn, telefone['id'])
    return por_id(conn, telefone['id'])


def familia_informou_ligado(conn, telefone, familia_id):
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone['id']).values(familia_ligou_em=agora()))
    auditoria.registrar(conn, 'familia_informou_ligado', 'familia', familia_id, 'telefone', telefone['id'])


# --- E7: XML ---

def amigos_para_teclas(conn, crianca, maximo=3):
    """Amigos aceitos, do mais antigo ao mais novo, para as teclas de discagem rapida."""
    from . import amizades as svc_ami
    lst = svc_ami.listar(conn, crianca['id'])
    amigos = sorted(lst['amigos'], key=lambda a: (a['desde'] or agora()))
    return [(a['apelido'], a['id_rede']) for a in amigos[:maximo]]


def gerar_xml(conn, telefone, cfg):
    crianca = svc_cri.por_id(conn, telefone['crianca_id'])
    tok = token_ativo(conn, telefone['id'])
    modelo_xml = 'ht' if telefone['modelo'] == 'ht' else 'grp'   # conta SIP: GRP usa os mesmos P-values base do GXP (confirmar em B09)
    pv = grandstream_xml.pvalues_sip(cfg.SIP_HOST, crianca['id_rede'], crianca['senha_sip'], crianca['apelido'], modelo_xml)
    if tok:
        pv.update(grandstream_xml.pvalues_provisionamento(url_provisionamento(cfg, tok['token']), cfg.PROV_INTERVALO_MIN, modelo_xml))
    pv.update(grandstream_xml.pvalues_travas(telefone['admin_senha'], modelo_xml))
    pv.update(grandstream_xml.pvalues_teclas(amigos_para_teclas(conn, crianca), modelo_xml))
    return grandstream_xml.gerar_xml(telefone['mac'], pv, versao=telefone['xml_versao'])


def gerar_xml_gdms(conn, telefone, cfg):
    """E5: XML que o GDMS entrega ao aparelho (device/config/xml).
    GDMS_XML_CONTEUDO='ponteiro': so o caminho do nosso servidor (P237 e companhia) e as travas;
    a conta SIP continua vindo do nosso servidor em E7, e a senha SIP nao passa pelo GDMS.
    'completo': o mesmo XML de E7 (fallback se a bancada B09 mostrar que o aparelho nao
    rebusca o P237 logo apos aplicar a configuracao do GDMS)."""
    if cfg.GDMS_XML_CONTEUDO == 'completo':
        return gerar_xml(conn, telefone, cfg)
    tok = token_ativo(conn, telefone['id'])
    if not tok:
        raise ValueError('telefone sem token de provisionamento ativo')
    modelo_xml = 'ht' if telefone['modelo'] == 'ht' else 'grp'
    pv = grandstream_xml.pvalues_provisionamento(url_provisionamento(cfg, tok['token']), cfg.PROV_INTERVALO_MIN, modelo_xml)
    pv.update(grandstream_xml.pvalues_travas(telefone['admin_senha'], modelo_xml))
    return grandstream_xml.gerar_xml(telefone['mac'], pv, versao=telefone['xml_versao'])


def entregar_config(conn, token, mac_pedido, ip, user_agent, cfg):
    """Chamado pelo endpoint /p/<token>/cfg<mac>.xml. Retorna (xml ou None, resultado)."""
    mac_n = re.sub(r'[^0-9A-Fa-f]', '', mac_pedido or '').upper()
    tok = conn.execute(select(db.prov_tokens).where(db.prov_tokens.c.token == (token or ''))).mappings().first()
    telefone = por_id(conn, tok['telefone_id']) if tok else None

    def log(resultado, xml=None):
        conn.execute(insert(db.prov_log).values(
            ts=agora(), ip=ip, user_agent=(user_agent or '')[:300], mac_pedido=mac_n or None,
            token_id=tok['id'] if tok else None, telefone_id=telefone['id'] if telefone else None,
            resultado=resultado, xml_versao=telefone['xml_versao'] if (telefone and xml) else None,
            xml_sha256=seguranca.sha256(xml) if xml else None, request_id=auditoria.request_id()))

    if not tok or not tok['ativo'] or not telefone:
        log('token_invalido')
        return None, 'token_invalido'
    if telefone['estado'] in ('desativado', 'erro_gdms_conflito'):
        log('estado_invalido')
        return None, 'estado_invalido'
    if mac_n != telefone['mac']:
        log('mac_nao_bate')
        auditoria.registrar(conn, 'prov_mac_nao_bate', 'telefone', mac_n, 'telefone', telefone['id'],
                            detalhes={'mac_pedido': mac_n, 'mac_cadastrado': telefone['mac']}, ip=ip, user_agent=user_agent)
        # Token usado por MAC diferente: se ja houve entrega para o MAC certo, e compartilhamento -> revogar
        if telefone['config_entregue_em']:
            revogar_tokens(conn, telefone['id'], 'token_compartilhado')
            _abrir_caso(conn, 'token_compartilhado', 'alta', telefone,
                        f'Token do telefone {telefone["id"]} usado por MAC {mac_n} (cadastrado {telefone["mac"]}). Token revogado.',
                        {'mac_pedido': mac_n})
            auditoria.registrar(conn, 'alerta_token_compartilhado', 'sistema', None, 'telefone', telefone['id'],
                                detalhes={'mac_pedido': mac_n})
        return None, 'mac_nao_bate'

    xml = gerar_xml(conn, telefone, cfg)
    log('entregue', xml)
    primeira = telefone['config_entregue_em'] is None
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone['id'])
                 .values(ultimo_prov_em=agora(), ultimo_prov_ip=ip, ultimo_prov_ua=(user_agent or '')[:300]))
    if estados.pode(telefone['estado'], 'config_entregue'):
        estados.transicionar(conn, telefone['id'], 'config_entregue', 'telefone', mac_n,
                             detalhes={'ip': ip, 'user_agent': (user_agent or '')[:120], 'xml_versao': telefone['xml_versao']})
    else:
        auditoria.registrar(conn, 'config_reentregue' if not primeira else 'config_entregue_fora_de_fluxo',
                            'telefone', mac_n, 'telefone', telefone['id'],
                            detalhes={'estado': telefone['estado'], 'xml_versao': telefone['xml_versao']}, ip=ip)
    # IP publico diferente do ultimo em pouco tempo
    if telefone['ultimo_prov_ip'] and telefone['ultimo_prov_ip'] != ip and telefone['ultimo_prov_em'] \
            and utc(telefone['ultimo_prov_em']) > agora() - timedelta(hours=24):
        _abrir_caso(conn, 'ip_divergente_prov', 'baixa', telefone,
                    f'Telefone {telefone["id"]} buscou config de {ip} e de {telefone["ultimo_prov_ip"]} em menos de 24h.',
                    {'ip_novo': ip, 'ip_anterior': telefone['ultimo_prov_ip']}, unico=True)
    return xml, 'entregue'


def _abrir_caso(conn, tipo, gravidade, telefone, descricao, detalhes=None, unico=False):
    if unico:
        existe = conn.execute(select(db.casos.c.id).where(and_(db.casos.c.tipo == tipo, db.casos.c.telefone_id == telefone['id'],
                                                               db.casos.c.estado == 'aberto'))).first()
        if existe:
            return existe[0]
    cr = svc_cri.por_id(conn, telefone['crianca_id'])
    return conn.execute(insert(db.casos).values(
        tipo=tipo, gravidade=gravidade, telefone_id=telefone['id'], crianca_id=telefone['crianca_id'],
        familia_id=cr['familia_id'] if cr else None, descricao=descricao, detalhes=detalhes or {},
        estado='aberto', criado_em=agora())).inserted_primary_key[0]


# --- E10 ---

def reconfigurar(conn, telefone, ator_tipo, ator_id, motivo):
    """Senha SIP nova + XML versao+1. O telefone pega na proxima checagem."""
    svc_cri.rotacionar_senha_sip(conn, telefone['crianca_id'], ator_tipo, ator_id, motivo)
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone['id'])
                 .values(xml_versao=telefone['xml_versao'] + 1, admin_senha=seguranca.senha_admin_aparelho()))
    auditoria.registrar(conn, 'reconfiguracao_solicitada', ator_tipo, ator_id, 'telefone', telefone['id'],
                        detalhes={'motivo': motivo, 'xml_versao': telefone['xml_versao'] + 1})


def desativar(conn, telefone_id, ator_tipo, ator_id, motivo, cfg, evento='desativar'):
    from . import gdms_fila
    t = por_id(conn, telefone_id)
    if not t or t['estado'] == 'desativado':
        return
    revogar_tokens(conn, telefone_id, motivo)
    gdms_fila.cancelar(conn, telefone_id)
    estados.transicionar(conn, telefone_id, evento, ator_tipo, ator_id, detalhes={'motivo': motivo})
    if t['gdms_cadastrado_em'] and cfg.GDMS_MODO != 'desligado':
        conn.execute(insert(db.tarefas).values(tipo='remover_gdms', telefone_id=telefone_id, estado='aberta', criado_em=agora(),
                                               descricao=f'Remover MAC {t["mac"]} da organização no GDMS ({motivo})'))


def reativar(conn, telefone, ator_tipo, ator_id, cfg):
    from . import gdms_fila
    if telefone['estado'] != 'desativado':
        raise ErroUsuario('Só é possível reativar um telefone desativado.')
    if por_mac_ativo(conn, telefone['mac']):
        raise ErroUsuario('Este MAC já está em uso por outro telefone.')
    estados.transicionar(conn, telefone['id'], 'reativar', ator_tipo, ator_id)
    _novo_token(conn, telefone['id'])
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone['id'])
                 .values(xml_versao=telefone['xml_versao'] + 1, informado_em=agora(), desativado_em=None))
    gdms_fila.enfileirar(conn, telefone['id'])


def senha_admin_consultada(conn, telefone, familia_id):
    auditoria.registrar(conn, 'senha_admin_consultada', 'familia', familia_id, 'telefone', telefone['id'])
    return telefone['admin_senha']


def status(conn, telefone, cfg):
    """Dados para a tela 'Conectando o telefone' e para o JSON de polling.

    A tela e um passo a passo com dono explicito: 'voce' (a familia faz) ou 'auto' (o portal, a
    Grandstream ou o proprio telefone fazem sozinhos). Cada passo tem um estado:
      feito | agora (vez da familia) | esperando (automatico em andamento) | erro | futuro.
    So um passo fica em 'agora'/'esperando'/'erro' por vez: e nele que a tela concentra a atencao."""
    from ..tempo import minutos_desde, texto_sp
    e = telefone['estado']
    t = telefone
    ligou = t['familia_ligou_em'] is not None or t['config_entregue_em'] is not None   # buscar config prova que ligou
    wifi = t['modelo'] == 'grpw'

    def p(chave, dono, titulo, feito_em=None, feito=None, **kw):
        ok = feito if feito is not None else (feito_em is not None)
        d = {'chave': chave, 'dono': dono, 'titulo': titulo, 'estado': 'feito' if ok else 'futuro',
             'quando': texto_sp(feito_em) if (ok and feito_em) else '', 'texto': '', 'espera': ''}
        d.update(kw)
        return d

    passos = [
        p('dados', 'voce', 'Informar o S/N e o MAC da etiqueta', t['informado_em']),
        p('gdms', 'auto', 'Registrar o telefone na Grandstream', t['gdms_cadastrado_em']),
        p('envio', 'auto', 'Guardar a configuração na Grandstream', t['config_enviada_em']),
        p('ligar', 'voce', 'Ligar o telefone e conectar ao Wi-Fi' if wifi else 'Ligar os cabos do telefone',
          t['familia_ligou_em'], feito=ligou),
        p('config', 'auto', 'O telefone liga e busca a configuração', t['config_entregue_em']),
        p('sip', 'auto', 'O telefone reinicia e se conecta à rede', t['registrado_em']),
        p('ativo', 'voce', 'Fazer a primeira ligação', t['ativo_em']),
    ]
    por = {d['chave']: d for d in passos}

    def atual(chave, estado, texto, espera=''):
        por[chave].update({'estado': estado, 'texto': texto, 'espera': espera})

    if e == 'dados_informados':
        atual('gdms', 'esperando', 'Estamos registrando o telefone na Grandstream. Nada a fazer por enquanto.',
              'Leva menos de 1 minuto.')
    elif e == 'gdms_cadastrado':
        atual('envio', 'esperando', 'Estamos enviando a configuração para a Grandstream guardar.', 'Leva menos de 1 minuto.')
    elif e == 'erro_dados':
        atual('gdms', 'erro', 'A Grandstream não reconheceu esse S/N e MAC juntos. Confira a etiqueta e corrija abaixo. '
              'O que parece a letra O costuma ser o número 0, e o que parece I costuma ser 1.')
    elif e == 'erro_gdms_conflito':
        atual('gdms', 'erro', 'Este telefone está registrado por outra empresa na Grandstream. Isso acontece com alguns '
              'revendedores. Peça ao vendedor para liberar o aparelho (informe o MAC) ou troque o aparelho.')
    elif e == 'aguardando_boot':
        if not ligou and wifi:
            atual('ligar', 'agora', 'Agora é com você. Ligue o fone e a energia como no desenho, conecte o telefone ao Wi-Fi '
                  'seguindo o passo a passo abaixo e depois clique em "Já liguei". Fora do Wi-Fi, não mexa em mais nada.')
        elif not ligou:
            atual('ligar', 'agora', 'Agora é com você. Ligue os três cabos como no desenho e depois clique em "Já liguei". '
                  'Não mexa no teclado do telefone.')
        else:
            m = minutos_desde(t['familia_ligou_em'] or t['config_enviada_em']) or 0
            if m > 10:
                atual('config', 'erro', 'Já faz mais de 10 minutos e o telefone não buscou a configuração. '
                      + ('Confira no visor se ele está conectado ao Wi-Fi (ícone de Wi-Fi sem X). Se não estiver, refaça o '
                         'passo a passo do Wi-Fi e confira a senha. ' if wifi else
                         'Confira se o cabo de rede está no roteador e se a luz da porta pisca. ')
                      + 'Depois desligue o telefone da tomada por 10 segundos e ligue de novo.', f'Esperando há {int(m)} min.')
            elif m > 3:
                atual('config', 'esperando', 'Está demorando um pouco mais que o normal. Desligue o telefone da tomada, '
                      'espere 10 segundos e ligue de novo. Não mexa no teclado.', f'Esperando há {int(m)} min.')
            else:
                atual('config', 'esperando', 'O telefone está ligando, falando com a Grandstream e buscando a configuração. '
                      'Nada a fazer: esta página atualiza sozinha.', 'Costuma levar de 1 a 3 minutos.')
    elif e == 'sem_boot':
        atual('config', 'erro', 'O telefone não buscou a configuração em 30 minutos. Já avisamos a equipe. Enquanto isso, '
              + ('confira o Wi-Fi no visor' if wifi else 'confira o cabo de rede')
              + ' e, se puder, faça o reset de fábrica pelo menu do telefone.')
    elif e == 'config_entregue':
        atual('sip', 'esperando', 'O telefone recebeu a configuração e está reiniciando. Nada a fazer.',
              'Costuma levar de 1 a 2 minutos.')
    elif e == 'sem_registro':
        atual('sip', 'erro', 'O telefone recebeu a configuração mas não conseguiu se conectar. Desligue e ligue o roteador '
              'e o telefone. Se não resolver, siga o passo a passo do SIP ALG abaixo.')
    elif e == 'registrado':
        atual('ativo', 'agora', 'Pronto. Tire o fone do gancho e disque 100# para ouvir a hora certa. Para falar com um '
              'amigo, autorize a amizade na aba Amigos e disque o ID dele.')
    elif e == 'ativo':
        pass

    indice_atual = next((i for i, d in enumerate(passos) if d['estado'] in ('agora', 'esperando', 'erro')), None)
    feitos = sum(1 for d in passos if d['estado'] == 'feito')
    dica = passos[indice_atual]['texto'] if indice_atual is not None else ('Tudo funcionando.' if e == 'ativo' else '')
    assinatura = '|'.join(f"{d['chave']}:{d['estado']}" for d in passos)
    return {'estado': e, 'passos': passos, 'dica': dica, 'mac': t['mac'], 'atual': indice_atual, 'feitos': feitos,
            'total': len(passos), 'assinatura': assinatura, 'wifi': wifi, 'modelo_nome': MODELOS_FAMILIA.get(t['modelo'], t['modelo']),
            'pode_informar_ligado': e == 'aguardando_boot' and not ligou}


def contar_por_estado(conn):
    rows = conn.execute(select(db.telefones.c.estado, func.count()).group_by(db.telefones.c.estado)).all()
    return {e: n for e, n in rows}
