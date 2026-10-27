"""
auditoria.py — Registro append-only de eventos (doc 09, secao 4).

registrar(conn, acao, ...) grava uma linha em audit_log na MESMA transacao da
acao de negocio. Segredos nunca entram: `detalhes` passa por redigir().
"""

import uuid

from flask import g, has_request_context
from sqlalchemy import select, and_, desc

from . import db
from .tempo import agora

CHAVES_SECRETAS = ('senha', 'password', 'senha_sip', 'admin_senha', 'token', 'access_token',
                   'refresh_token', 'client_secret', 'signature', 'senha_hash', 'codigo')


def redigir(obj):
    if isinstance(obj, dict):
        return {k: ('***' if any(s in k.lower() for s in CHAVES_SECRETAS) else redigir(v))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redigir(v) for v in obj]
    return obj


def request_id():
    if has_request_context() and getattr(g, 'request_id', None):
        return g.request_id
    rid = getattr(g, 'request_id', None) if has_request_context() else None
    return rid or str(uuid.uuid4())


def contexto_request():
    if has_request_context():
        return getattr(g, 'ip', None), getattr(g, 'user_agent', None)
    return None, None


def registrar(conn, acao, ator_tipo='sistema', ator_id=None, objeto_tipo=None, objeto_id=None,
              detalhes=None, ip=None, user_agent=None, corrige_id=None, rid=None):
    if ator_tipo not in ('familia', 'sistema', 'operador', 'telefone', 'gdms'):
        raise ValueError(f'ator_tipo invalido: {ator_tipo}')
    ip_req, ua_req = contexto_request()
    r = conn.execute(db.audit_log.insert().values(
        ts=agora(), request_id=rid or request_id(), ator_tipo=ator_tipo,
        ator_id=None if ator_id is None else str(ator_id),
        acao=acao, objeto_tipo=objeto_tipo,
        objeto_id=None if objeto_id is None else str(objeto_id),
        ip=ip or ip_req, user_agent=user_agent or ua_req,
        detalhes=redigir(detalhes) if detalhes is not None else None,
        corrige_id=corrige_id,
    ))
    return r.inserted_primary_key[0]


def consultar(conn, operador_email, acao=None, objeto_tipo=None, objeto_id=None,
              request_id_filtro=None, limite=200):
    """Consulta de auditoria pelo operador. A consulta em si e registrada."""
    conds = []
    if acao:
        conds.append(db.audit_log.c.acao == acao)
    if objeto_tipo:
        conds.append(db.audit_log.c.objeto_tipo == objeto_tipo)
    if objeto_id:
        conds.append(db.audit_log.c.objeto_id == str(objeto_id))
    if request_id_filtro:
        conds.append(db.audit_log.c.request_id == request_id_filtro)
    q = select(db.audit_log).order_by(desc(db.audit_log.c.id)).limit(limite)
    if conds:
        q = q.where(and_(*conds))
    linhas = conn.execute(q).mappings().all()
    registrar(conn, 'auditoria_consultada', 'operador', operador_email,
              detalhes={'acao': acao, 'objeto_tipo': objeto_tipo, 'objeto_id': objeto_id,
                        'request_id': request_id_filtro, 'linhas': len(linhas)})
    return linhas


def linha_do_tempo(conn, telefone_id=None, crianca_id=None, familia_id=None, limite=500):
    """Todos os eventos ligados a um telefone (audit + estados + prov + gdms), em ordem."""
    eventos = []
    if telefone_id is not None:
        for r in conn.execute(select(db.device_state_history)
                              .where(db.device_state_history.c.telefone_id == telefone_id)).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'estado', 'texto': f"{r['de'] or '(início)'} para {r['para']} ({r['evento']})",
                            'ator': f"{r['ator_tipo']}:{r['ator_id'] or ''}"})
        for r in conn.execute(select(db.prov_log).where(db.prov_log.c.telefone_id == telefone_id)).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'prov', 'texto': f"{r['resultado']} mac={r['mac_pedido']} v={r['xml_versao']} ip={r['ip']}",
                            'ator': 'telefone'})
        for r in conn.execute(select(db.gdms_log).where(db.gdms_log.c.telefone_id == telefone_id)).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'gdms', 'texto': f"{r['metodo']} {r['endpoint']} retCode={r['ret_code']} {r['msg'] or ''}",
                            'ator': 'sistema'})
        for r in conn.execute(select(db.audit_log).where(and_(db.audit_log.c.objeto_tipo == 'telefone',
                                                              db.audit_log.c.objeto_id == str(telefone_id)))).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'audit', 'texto': r['acao'], 'ator': f"{r['ator_tipo']}:{r['ator_id'] or ''}",
                            'detalhes': r['detalhes']})
    if crianca_id is not None:
        for r in conn.execute(select(db.audit_log).where(and_(db.audit_log.c.objeto_tipo == 'crianca',
                                                              db.audit_log.c.objeto_id == str(crianca_id)))).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'audit', 'texto': r['acao'], 'ator': f"{r['ator_tipo']}:{r['ator_id'] or ''}",
                            'detalhes': r['detalhes']})
    if familia_id is not None:
        for r in conn.execute(select(db.audit_log).where(and_(db.audit_log.c.objeto_tipo == 'familia',
                                                              db.audit_log.c.objeto_id == str(familia_id)))).mappings():
            eventos.append({'ts': r['ts'], 'fonte': 'audit', 'texto': r['acao'], 'ator': f"{r['ator_tipo']}:{r['ator_id'] or ''}",
                            'detalhes': r['detalhes']})
    eventos.sort(key=lambda e: (e['ts'] or agora()))
    return eventos[:limite]
