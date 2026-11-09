"""filtros.py — filtros Jinja."""

from datetime import datetime

from flask import g

from ..tempo import em_fuso, TZ_SP
from .. import ids

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def registrar(app):
    @app.template_filter('datahora')
    def datahora(v):
        """'2026-03-05 16:20:55' (texto SP, como o Asterisk grava) ou datetime -> '5 mar 16:20', no fuso da
        familia logada (familias.fuso); sem familia (ONG), Sao Paulo."""
        try:
            try:
                fuso = g.familia['fuso'] if getattr(g, 'familia', None) else None
            except RuntimeError:   # fora de requisicao
                fuso = None
            if not isinstance(v, datetime):
                v = TZ_SP.localize(datetime.strptime(v, '%Y-%m-%d %H:%M:%S'))
            d = em_fuso(v, fuso)
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
