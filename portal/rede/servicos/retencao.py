"""
retencao.py — Prazos de guarda prometidos na politica de privacidade (doc 13).

aplicar(conn, cfg): roda no job diario.
  - call_logs com mais de RETENCAO_CHAMADAS_DIAS: somados em chamadas_resumo (por dia) e apagados.
As tabelas somente-acrescimo (prov_log, gdms_log, device_state_history, audit_log) nao podem ser
alteradas pelo papel do portal; a retencao delas e feita no banco por deploy/retencao.sql (cron diario).
"""

from datetime import timedelta

from sqlalchemy import select, delete, insert, update, func, text

from .. import db, auditoria
from ..tempo import agora, em_sp


def aplicar(conn, cfg, ref=None):
    ref = ref or agora()
    limite = em_sp(ref - timedelta(days=cfg.RETENCAO_CHAMADAS_DIAS)).strftime('%Y-%m-%d 00:00:00')
    antigas = conn.execute(text(
        "SELECT substr(timestamp, 1, 10) AS dia, count(*) AS n, "
        "coalesce(sum(CASE WHEN status = 'ALLOWED' THEN coalesce(duration_seconds, 0) ELSE 0 END), 0) AS segs, "
        "sum(CASE WHEN status = 'BLOCKED' THEN 1 ELSE 0 END) AS bloq "
        "FROM call_logs WHERE timestamp < :lim GROUP BY dia"), {'lim': limite}).all()
    total = 0
    for dia, n, segs, bloq in antigas:
        atual = conn.execute(select(db.chamadas_resumo).where(db.chamadas_resumo.c.dia == dia)).mappings().first()
        if atual:
            conn.execute(update(db.chamadas_resumo).where(db.chamadas_resumo.c.dia == dia).values(
                chamadas=atual['chamadas'] + int(n), segundos=atual['segundos'] + int(segs or 0),
                bloqueadas=atual['bloqueadas'] + int(bloq or 0)))
        else:
            conn.execute(insert(db.chamadas_resumo).values(dia=dia, chamadas=int(n), segundos=int(segs or 0),
                                                            bloqueadas=int(bloq or 0)))
        total += int(n)
    if total:
        conn.execute(delete(db.call_logs).where(db.call_logs.c.timestamp < limite))
        auditoria.registrar(conn, 'retencao_chamadas_aplicada', 'sistema', detalhes={'apagadas': total, 'antes_de': limite})
    return {'chamadas_apagadas': total, 'dias': len(antigas)}


def apagar_chamadas_de(conn, ids_rede):
    """Exclusao de conta: as ligacoes das criancas removidas saem do historico (os totais por dia ja
    contemplam so o que passou da retencao; o resto e apagado sem agregar, para nao manter vinculo)."""
    if not ids_rede:
        return 0
    r = conn.execute(delete(db.call_logs).where(db.call_logs.c.caller_ext.in_(list(ids_rede)) |
                                                db.call_logs.c.callee_ext.in_(list(ids_rede))))
    return r.rowcount
