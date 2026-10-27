"""filtros.py — filtros Jinja."""

from datetime import datetime

from ..tempo import em_sp
from .. import ids

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def registrar(app):
    @app.template_filter('datahora')
    def datahora(v):
        """'2026-03-05 16:20:55' (texto SP) ou datetime -> '5 mar 16:20'."""
        try:
            if isinstance(v, datetime):
                d = em_sp(v)
            else:
                d = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
            return f'{d.day} {MESES[d.month - 1]} {d.hour:02d}:{d.minute:02d}'
        except (ValueError, TypeError, AttributeError):
            return v or ''

    @app.template_filter('idfmt')
    def idfmt(v):
        try:
            return ids.formatar_id(v)
        except ValueError:
            return v

    @app.template_filter('mac')
    def macfmt(v):
        # Mostra como esta impresso na etiqueta do aparelho (12 caracteres, sem dois-pontos),
        # para a familia conferir letra por letra.
        return (v or '').upper()

    @app.template_filter('duracao')
    def duracao(s):
        s = int(s or 0)
        if s >= 3600:
            return f'{s // 3600}h {(s % 3600) // 60}min'
        if s >= 60:
            return f'{s // 60}min {s % 60}s'
        return f'{s}s'
