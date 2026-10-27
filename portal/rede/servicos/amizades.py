"""amizades.py — Pedidos de amizade por ID, com aceite da outra familia. Base da autorizacao mutua."""

from datetime import timedelta

from sqlalchemy import select, insert, update, and_, or_, func

from .. import db, auditoria, ids
from ..tempo import agora
from .contas import ErroUsuario
from . import criancas as svc_cri


def _par(conn, a, b):
    """Linha de amizade entre a e b, em qualquer direcao, nao removida."""
    return conn.execute(select(db.amizades).where(and_(
        or_(and_(db.amizades.c.de_crianca_id == a, db.amizades.c.para_crianca_id == b),
            and_(db.amizades.c.de_crianca_id == b, db.amizades.c.para_crianca_id == a)),
        db.amizades.c.estado != 'removida'))).mappings().first()


MENSAGEM_MAX = 80


def limpar_mensagem(texto):
    """Apresentacao curta de quem pede ('Joao, 4a serie da Escola X'). Uma linha, ate 80 caracteres,
    sem controle. Vazio vira None. E a unica informacao livre que uma familia manda a outra."""
    t = ' '.join((texto or '').split())
    if len(t) > MENSAGEM_MAX:
        raise ErroUsuario(f'A mensagem pode ter no máximo {MENSAGEM_MAX} caracteres.')
    return t or None


def pedir(conn, crianca, id_rede_destino, familia_id, cfg, mailer=None, mensagem=None, sem_limites=False):
    mensagem = limpar_mensagem(mensagem)
    id_dest = ''.join(ch for ch in (id_rede_destino or '') if ch.isdigit())
    if not ids.ID_RE.match(id_dest):
        raise ErroUsuario('ID inválido. São 6 números, por exemplo 34 56 78.')
    if id_dest == crianca['id_rede']:
        raise ErroUsuario('Esse é o ID da própria criança.')
    dest = svc_cri.por_id_rede(conn, id_dest)
    # Limites antes de revelar qualquer coisa
    pend = conn.execute(select(func.count()).select_from(db.amizades).where(and_(
        db.amizades.c.de_crianca_id == crianca['id'], db.amizades.c.estado == 'pendente'))).scalar()
    if pend >= cfg.LIMITE_PEDIDOS_PENDENTES and not sem_limites:
        raise ErroUsuario('Você tem muitos pedidos aguardando resposta. Espere as outras famílias responderem.')
    hoje = conn.execute(select(func.count()).select_from(db.amizades).join(db.criancas, db.criancas.c.id == db.amizades.c.de_crianca_id)
                        .where(and_(db.criancas.c.familia_id == familia_id,
                                    db.amizades.c.criado_em > agora() - timedelta(days=1)))).scalar()
    if hoje >= cfg.LIMITE_PEDIDOS_DIA and not sem_limites:
        auditoria.registrar(conn, 'suspeita_pedidos_massa', 'sistema', None, 'familia', familia_id)
        raise ErroUsuario('Limite diário de pedidos atingido.')
    if not dest or not dest['ativa']:
        auditoria.registrar(conn, 'pedido_amizade_id_inexistente', 'familia', familia_id, 'crianca', crianca['id'],
                            detalhes={'id_destino': id_dest})
        raise ErroUsuario('Não encontramos esse ID. Confira com a outra família.')
    existente = _par(conn, crianca['id'], dest['id'])
    if existente:
        if existente['estado'] == 'bloqueada':
            # Silencioso: nao revelar bloqueio
            auditoria.registrar(conn, 'pedido_amizade_a_bloqueado', 'familia', familia_id, 'crianca', crianca['id'],
                                detalhes={'destino': dest['id']})
            return None
        if existente['estado'] == 'aceita':
            raise ErroUsuario(f'{dest["apelido"]} já é amigo.')
        if existente['estado'] == 'pendente':
            if existente['de_crianca_id'] == crianca['id']:
                raise ErroUsuario('Pedido já enviado. Aguarde a outra família responder.')
            # O outro lado ja pediu: aceitar
            return responder(conn, existente['id'], familia_id, 'aceitar')
        if existente['estado'] == 'recusada' and existente['recusas'] >= 2:
            auditoria.registrar(conn, 'pedido_amizade_recusado_repetido', 'familia', familia_id, 'crianca', crianca['id'],
                                detalhes={'destino': dest['id']})
            return None  # bloqueio silencioso
        conn.execute(update(db.amizades).where(db.amizades.c.id == existente['id'])
                     .values(de_crianca_id=crianca['id'], para_crianca_id=dest['id'], estado='pendente',
                             criado_em=agora(), respondido_em=None, mensagem=mensagem))
        aid = existente['id']
    else:
        aid = conn.execute(insert(db.amizades).values(de_crianca_id=crianca['id'], para_crianca_id=dest['id'],
                                                      estado='pendente', criado_em=agora(), mensagem=mensagem)).inserted_primary_key[0]
    auditoria.registrar(conn, 'pedido_amizade_enviado', 'familia', familia_id, 'crianca', crianca['id'],
                        detalhes={'destino': dest['id'], 'amizade_id': aid})
    _avisar(conn, dest, crianca, cfg, mailer, mensagem)
    return conn.execute(select(db.amizades).where(db.amizades.c.id == aid)).mappings().first()


def _avisar(conn, dest, origem, cfg, mailer, mensagem=None):
    if mailer is None:
        try:
            from flask import current_app
            mailer = current_app.mailer
        except RuntimeError:
            return
    fam = conn.execute(select(db.familias).where(db.familias.c.id == dest['familia_id'])).mappings().first()
    if fam and '@' in fam['email']:
        mailer.enviar(fam['email'], f'{origem["apelido"]} quer ser amigo de {dest["apelido"]} na {cfg.NOME_REDE}',
                      f'A família de {origem["apelido"]} (ID {ids.formatar_id(origem["id_rede"])}) pediu para ligar para '
                      f'{dest["apelido"]}.\n\n'
                      + (f'Quem está pedindo: "{mensagem}"\n\n' if mensagem else '')
                      + f'Aceite ou recuse em {cfg.SITE_URL}/crianca/{dest["id"]}/contatos\n\n'
                      f'Se você não conhece essa criança, basta recusar.')


def responder(conn, amizade_id, familia_id, acao):
    a = conn.execute(select(db.amizades).where(db.amizades.c.id == amizade_id)).mappings().first()
    if not a:
        raise ErroUsuario('Pedido não encontrado.')
    minha = svc_cri.por_id(conn, a['para_crianca_id'])
    outra = svc_cri.por_id(conn, a['de_crianca_id'])
    if acao == 'bloquear' or acao == 'remover':
        # Qualquer um dos dois lados pode bloquear/remover
        if familia_id not in (minha['familia_id'], outra['familia_id']):
            raise ErroUsuario('Pedido não encontrado.')
    elif not minha or minha['familia_id'] != familia_id:
        raise ErroUsuario('Pedido não encontrado.')
    if acao == 'aceitar':
        if a['estado'] != 'pendente':
            raise ErroUsuario('Este pedido já foi respondido.')
        novo = 'aceita'
        vals = {'estado': novo, 'respondido_em': agora()}
    elif acao == 'recusar':
        if a['estado'] != 'pendente':
            raise ErroUsuario('Este pedido já foi respondido.')
        novo = 'recusada'
        vals = {'estado': novo, 'respondido_em': agora(), 'recusas': a['recusas'] + 1}
    elif acao == 'bloquear':
        novo = 'bloqueada'
        # Quem bloqueia vira o 'para' (alvo do bloqueio e o 'de')
        bloqueador = minha if minha['familia_id'] == familia_id else outra
        bloqueado = outra if bloqueador['id'] == minha['id'] else minha
        vals = {'estado': novo, 'respondido_em': agora(), 'de_crianca_id': bloqueado['id'], 'para_crianca_id': bloqueador['id']}
    elif acao == 'remover':
        novo = 'removida'
        vals = {'estado': novo, 'respondido_em': agora()}
    else:
        raise ErroUsuario('Ação inválida.')
    conn.execute(update(db.amizades).where(db.amizades.c.id == amizade_id).values(**vals))
    auditoria.registrar(conn, f'amizade_{novo}', 'familia', familia_id, 'amizade', amizade_id,
                        detalhes={'de': a['de_crianca_id'], 'para': a['para_crianca_id']})
    if novo in ('aceita', 'removida', 'bloqueada'):
        from . import gdms_fila
        for cid in (a['de_crianca_id'], a['para_crianca_id']):
            gdms_fila.atualizar_teclas(conn, cid)      # teclas de discagem rapida dos dois telefones
    return conn.execute(select(db.amizades).where(db.amizades.c.id == amizade_id)).mappings().first()


def desbloquear(conn, amizade_id, familia_id):
    a = conn.execute(select(db.amizades).where(db.amizades.c.id == amizade_id)).mappings().first()
    if not a or a['estado'] != 'bloqueada':
        raise ErroUsuario('Bloqueio não encontrado.')
    quem = svc_cri.por_id(conn, a['para_crianca_id'])
    if quem['familia_id'] != familia_id:
        raise ErroUsuario('Bloqueio não encontrado.')
    conn.execute(update(db.amizades).where(db.amizades.c.id == amizade_id).values(estado='removida', respondido_em=agora()))
    auditoria.registrar(conn, 'amizade_desbloqueada', 'familia', familia_id, 'amizade', amizade_id)


def listar(conn, crianca_id):
    """Contatos da crianca: aceitas, pedidos recebidos, pedidos enviados, bloqueios feitos por ela."""
    rows = conn.execute(select(db.amizades).where(and_(
        or_(db.amizades.c.de_crianca_id == crianca_id, db.amizades.c.para_crianca_id == crianca_id),
        db.amizades.c.estado.in_(('pendente', 'aceita', 'bloqueada'))))).mappings().all()
    out = {'amigos': [], 'recebidos': [], 'enviados': [], 'bloqueados': []}
    for a in rows:
        outro_id = a['para_crianca_id'] if a['de_crianca_id'] == crianca_id else a['de_crianca_id']
        outro = svc_cri.por_id(conn, outro_id)
        item = {'amizade_id': a['id'], 'apelido': outro['apelido'] if outro else '?',
                'id_rede': outro['id_rede'] if outro else '', 'id_fmt': ids.formatar_id(outro['id_rede']) if outro else '',
                'desde': a['respondido_em'] or a['criado_em'], 'mensagem': a['mensagem'] if a['estado'] == 'pendente' else None}
        if a['estado'] == 'aceita':
            out['amigos'].append(item)
        elif a['estado'] == 'pendente':
            (out['recebidos'] if a['para_crianca_id'] == crianca_id else out['enviados']).append(item)
        elif a['estado'] == 'bloqueada' and a['para_crianca_id'] == crianca_id:
            out['bloqueados'].append(item)
    return out


def permitido(conn, id_rede_a, id_rede_b):
    """Autorizacao mutua para o AGI: existe amizade aceita entre os dois IDs."""
    a = svc_cri.por_id_rede(conn, id_rede_a)
    b = svc_cri.por_id_rede(conn, id_rede_b)
    if not a or not b or not a['ativa'] or not b['ativa']:
        return False
    par = _par(conn, a['id'], b['id'])
    return bool(par and par['estado'] == 'aceita')
