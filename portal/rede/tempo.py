"""tempo.py — Datas sempre em UTC no banco; exibicao em America/Sao_Paulo."""

from datetime import datetime, timezone

import pytz

TZ_SP = pytz.timezone('America/Sao_Paulo')


def agora():
    return datetime.now(timezone.utc)


def utc(dt):
    """Garante datetime aware em UTC (SQLite devolve naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def em_sp(dt):
    dt = utc(dt)
    return dt.astimezone(TZ_SP) if dt else None


def minutos_desde(dt, ref=None):
    dt = utc(dt)
    if dt is None:
        return None
    return ((utc(ref) or agora()) - dt).total_seconds() / 60.0


def texto_sp(dt, fmt='%d/%m %H:%M'):
    d = em_sp(dt)
    return d.strftime(fmt) if d else ''


def agora_sp_texto():
    return datetime.now(TZ_SP).strftime('%Y-%m-%d %H:%M:%S')
