"""horarios.py — Horarios permitidos por dia da semana. Sem horario = liberado o dia todo."""

import re

from datetime import timedelta

from sqlalchemy import select, insert, delete, update, and_

from .. import db, auditoria
from ..tempo import agora, utc, em_sp, TZ_SP
from .contas import ErroUsuario

TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def listar(conn, crianca_id):
    return conn.execute(select(db.horarios).where(db.horarios.c.crianca_id == crianca_id)
                        .order_by(db.horarios.c.dia_semana)).mappings().all()


def salvar(conn, crianca_id, padroes, familia_id):
    """padroes: lista de {'inicio': 'HH:MM', 'fim': 'HH:MM', 'dias': [0..6]}. Substitui tudo."""
    for p in padroes:
        if not TIME_RE.match(p['inicio']) or not TIME_RE.match(p['fim']):
            raise ErroUsuario('Horário inválido.')
        if p['inicio'] >= p['fim']:
            raise ErroUsuario('O horário de fim deve ser depois do início.')
    conn.execute(delete(db.horarios).where(db.horarios.c.crianca_id == crianca_id))
    vistos = set()
    for p in padroes:
        for d in p['dias']:
            d = int(d)
            if d < 0 or d > 6 or d in vistos:
                continue
            vistos.add(d)
            conn.execute(insert(db.horarios).values(crianca_id=crianca_id, dia_semana=d, inicio=p['inicio'], fim=p['fim']))
    auditoria.registrar(conn, 'horarios_salvos', 'familia', familia_id, 'crianca', crianca_id,
                        detalhes={'padroes': padroes})


DURACOES_SILENCIO = {'1h': 'por 1 hora', '2h': 'por 2 horas', '4h': 'por 4 horas', 'manha': 'até amanhã às 8h'}


def silenciar(conn, crianca_id, duracao, familia_id):
    """'Nao perturbe' imediato: o telefone nao faz nem recebe ligacoes ate o instante calculado.
    Complementa os horarios fixos (ex.: visita, castigo, dever de casa). Item 3 do doc 12."""
    if duracao not in DURACOES_SILENCIO:
        raise ErroUsuario('Duração inválida.')
    ref = agora()
    if duracao == 'manha':
        sp = em_sp(ref)
        proxima = (sp + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        ate = proxima
    else:
        ate = ref + timedelta(hours=int(duracao[:-1]))
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(nao_perturbe_ate=ate))
    auditoria.registrar(conn, 'silencio_ligado', 'familia', familia_id, 'crianca', crianca_id,
                        detalhes={'duracao': duracao, 'ate': utc(ate).isoformat()})
    return ate


def reativar(conn, crianca_id, familia_id):
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(nao_perturbe_ate=None))
    auditoria.registrar(conn, 'silencio_desligado', 'familia', familia_id, 'crianca', crianca_id)


def silencio_ativo(crianca, ref=None):
    """Instante (UTC) ate quando esta silenciado, ou None se nao esta."""
    ate = utc(crianca['nao_perturbe_ate']) if crianca else None
    if ate and ate > (ref or agora()):
        return ate
    return None


def dentro_do_horario(conn, id_rede, agora_sp):
    """Para o AGI. Sem horario no dia = liberado. 'Nao perturbe' vale antes de tudo."""
    c = conn.execute(select(db.criancas.c.id, db.criancas.c.nao_perturbe_ate).where(db.criancas.c.id_rede == id_rede)).mappings().first()
    if not c:
        return False
    if silencio_ativo(c, utc(agora_sp)):
        return False
    dia = agora_sp.weekday()
    hhmm = agora_sp.strftime('%H:%M')
    rows = conn.execute(select(db.horarios).where(and_(db.horarios.c.crianca_id == c['id'],
                                                       db.horarios.c.dia_semana == dia))).mappings().all()
    if not rows:
        return True
    return any(r['inicio'] <= hhmm < r['fim'] for r in rows)


def agrupar(rows):
    """Para a tela: agrupa por (inicio, fim) -> dias."""
    pats = {}
    for r in rows:
        pats.setdefault((r['inicio'], r['fim']), []).append(r['dia_semana'])
    return [{'sh': int(i.split(':')[0]), 'sm': int(i.split(':')[1]), 'eh': int(f.split(':')[0]),
             'em': int(f.split(':')[1]), 'days': sorted(d)} for (i, f), d in pats.items()]
