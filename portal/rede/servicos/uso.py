"""uso.py — Quadro de uso da rede para o painel do operador, sem discriminar criança.

Conta telefones (cadastrados, conectados agora, que já ligaram) e ligações por tipo (criança com criança,
criança para celular, celular para criança) no mês atual e no anterior. Só totais: quem ligou para quem
fica no histórico de cada família, não aqui."""

import math

from sqlalchemy import select, func, text

from .. import db
from ..tempo import agora, em_sp
from . import telefones as svc_tel

TIPOS = (('crianca_crianca', 'Telefone com telefone'),
         ('crianca_celular', 'Telefone para celular'),
         ('celular_crianca', 'Celular para telefone'))


def _tipo(caller, callee):
    if len(caller) == 6 and len(callee) == 6:
        return 'crianca_crianca'
    if len(callee) == 7 and callee[0] in '98':
        return 'crianca_celular'
    if caller.isdigit() and len(caller) in (10, 11):
        return 'celular_crianca'
    return None


def _mes_anterior(hoje):
    ano, mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    return f'{ano:04d}-{mes:02d}'


def _ligacoes_do_mes(conn, mes):
    rows = conn.execute(text("SELECT caller_ext, callee_ext, status, duration_seconds FROM call_logs WHERE timestamp LIKE :m"),
                        {'m': mes + '%'}).mappings().all()
    out = {t: {'ligacoes': 0, 'minutos': 0, 'nao_completadas': 0, 'segundos': 0} for t, _ in TIPOS}
    for r in rows:
        t = _tipo(r['caller_ext'] or '', r['callee_ext'] or '')
        if not t:
            continue
        if r['status'] == 'ALLOWED' and r['duration_seconds']:
            out[t]['ligacoes'] += 1
            out[t]['segundos'] += r['duration_seconds']
        else:
            out[t]['nao_completadas'] += 1
    for t in out:
        out[t]['minutos'] = int(math.ceil(out[t].pop('segundos') / 60)) if out[t]['ligacoes'] else 0
    return out


def resumo(conn, ref=None):
    hoje = em_sp(ref or agora())
    mes, anterior = hoje.strftime('%Y-%m'), _mes_anterior(hoje)
    cadastrados = conn.execute(select(func.count()).select_from(db.telefones)
                               .where(db.telefones.c.estado.notin_(svc_tel.ESTADOS_REMOVIDO))).scalar()
    ativos = conn.execute(select(func.count()).select_from(db.telefones).where(db.telefones.c.estado == 'ativo')).scalar()
    conectados = None
    if db.tabela_existe(conn, 'ps_contacts'):
        conectados = conn.execute(text("SELECT count(*) FROM ps_contacts WHERE length(endpoint) = 6")).scalar()
    return {'mes': mes, 'mes_anterior': anterior,
            'telefones': {'cadastrados': cadastrados, 'conectados': conectados, 'ativos': ativos},
            'tipos': TIPOS, 'atual': _ligacoes_do_mes(conn, mes), 'anterior': _ligacoes_do_mes(conn, anterior)}
