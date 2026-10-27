"""criancas.py — E2: apelido + ID + ramal (ps_endpoints/ps_auths/ps_aors) na mesma transacao."""

from sqlalchemy import select, insert, update, delete, and_

from .. import db, auditoria, seguranca, ids
from ..tempo import agora
from .contas import ErroUsuario

CONTEXTO_DIALPLAN = 'telefones-criancas'


def listar(conn, familia_id, incluir_inativas=False):
    q = select(db.criancas).where(db.criancas.c.familia_id == familia_id)
    if not incluir_inativas:
        q = q.where(db.criancas.c.ativa == True)  # noqa: E712
    return conn.execute(q.order_by(db.criancas.c.id)).mappings().all()


def por_id(conn, crianca_id):
    return conn.execute(select(db.criancas).where(db.criancas.c.id == crianca_id)).mappings().first()


def por_id_rede(conn, id_rede):
    return conn.execute(select(db.criancas).where(db.criancas.c.id_rede == id_rede)).mappings().first()


def da_familia(conn, familia_id, crianca_id):
    c = por_id(conn, crianca_id)
    if not c or c['familia_id'] != familia_id or not c['ativa']:
        return None
    return c


def _id_existe(conn):
    def f(candidato):
        return conn.execute(select(db.criancas.c.id).where(db.criancas.c.id_rede == candidato)).first() is not None
    return f


def criar(conn, familia_id, apelido, cfg, ator_id=None):
    try:
        apelido = ids.validar_nick(apelido)
    except ValueError as e:
        auditoria.registrar(conn, 'apelido_rejeitado', 'familia', familia_id, 'familia', familia_id,
                            detalhes={'motivo': str(e)})
        raise ErroUsuario(str(e))
    if conn.execute(select(db.criancas.c.id).where(db.criancas.c.apelido == apelido)).first():
        auditoria.registrar(conn, 'apelido_rejeitado', 'familia', familia_id, 'familia', familia_id,
                            detalhes={'motivo': 'ja_existe'})
        raise ErroUsuario('Esse apelido já está em uso. Escolha outro.')
    if len(listar(conn, familia_id)) >= 6:
        raise ErroUsuario('Limite de crianças por conta atingido.')
    id_rede = ids.gerar_id(_id_existe(conn))
    senha = seguranca.senha_sip()
    r = conn.execute(insert(db.criancas).values(familia_id=familia_id, apelido=apelido, id_rede=id_rede,
                                                senha_sip=senha, criado_em=agora(), ativa=True))
    cid = r.inserted_primary_key[0]
    _criar_ramal(conn, id_rede, senha, apelido)
    auditoria.registrar(conn, 'crianca_criada', 'familia', ator_id or familia_id, 'crianca', cid,
                        detalhes={'id_rede': id_rede, 'apelido': apelido})
    auditoria.registrar(conn, 'ramal_criado', 'sistema', None, 'crianca', cid,
                        detalhes={'id_rede': id_rede, 'senha_sip_sha256': seguranca.sha256(senha)})
    return por_id(conn, cid)


def _criar_ramal(conn, id_rede, senha, apelido):
    conn.execute(insert(db.ps_endpoints).values(
        id=id_rede, transport='transport-tcp', aors=id_rede, auth=id_rede, context=CONTEXTO_DIALPLAN,
        disallow='all', allow='g722,ulaw,alaw', direct_media='no', rtp_symmetric='yes', force_rport='yes',
        rewrite_contact='yes', callerid=f'{apelido} <{id_rede}>', dtmf_mode='rfc4733'))
    conn.execute(insert(db.ps_auths).values(id=id_rede, auth_type='userpass', username=id_rede, password=senha))
    conn.execute(insert(db.ps_aors).values(id=id_rede, max_contacts=1, remove_existing='yes',
                                          default_expiration=120, qualify_frequency=60))


def rotacionar_senha_sip(conn, crianca_id, ator_tipo, ator_id, motivo):
    c = por_id(conn, crianca_id)
    nova = seguranca.senha_sip()
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(senha_sip=nova))
    conn.execute(update(db.ps_auths).where(db.ps_auths.c.id == c['id_rede']).values(password=nova))
    auditoria.registrar(conn, 'senha_sip_rotacionada', ator_tipo, ator_id, 'crianca', crianca_id,
                        detalhes={'motivo': motivo, 'senha_sip_sha256': seguranca.sha256(nova)})
    return nova


def desativar(conn, crianca_id, ator_tipo, ator_id):
    c = por_id(conn, crianca_id)
    if not c:
        return
    for t in (db.ps_endpoints, db.ps_auths, db.ps_aors):
        conn.execute(delete(t).where(t.c.id == c['id_rede']))
    conn.execute(delete(db.amizades).where((db.amizades.c.de_crianca_id == crianca_id) |
                                           (db.amizades.c.para_crianca_id == crianca_id)))
    conn.execute(delete(db.horarios).where(db.horarios.c.crianca_id == crianca_id))
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(
        ativa=False, desativada_em=agora(), apelido=f'removido-{crianca_id}', senha_sip='x'))
    auditoria.registrar(conn, 'crianca_desativada', ator_tipo, ator_id, 'crianca', crianca_id,
                        detalhes={'id_rede': c['id_rede']})


def ramal_consistente(conn, crianca):
    """Para a reconciliacao: as tres linhas ps_* existem para a crianca ativa?"""
    idr = crianca['id_rede']
    e = conn.execute(select(db.ps_endpoints.c.id).where(db.ps_endpoints.c.id == idr)).first()
    a = conn.execute(select(db.ps_auths.c.id).where(db.ps_auths.c.id == idr)).first()
    o = conn.execute(select(db.ps_aors.c.id).where(db.ps_aors.c.id == idr)).first()
    return bool(e and a and o)
