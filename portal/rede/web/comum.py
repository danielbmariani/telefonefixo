"""comum.py — decorators e helpers compartilhados pelos blueprints."""

import functools

from flask import session, redirect, url_for, abort, g, current_app, flash

from .. import db
from ..servicos import contas, criancas as svc_cri


def conn():
    return db.conexao()


def login_obrigatorio(f):
    @functools.wraps(f)
    def w(*a, **kw):
        if 'familia_id' not in session:
            return redirect(url_for('auth.entrar'))
        fam = contas.por_id(conn(), session['familia_id'])
        if not fam or fam['suspensa']:
            session.clear()
            return redirect(url_for('auth.entrar'))
        g.familia = fam
        return f(*a, **kw)
    return w


def consentimento_obrigatorio(f):
    @functools.wraps(f)
    def w(*a, **kw):
        if contas.consentimentos_pendentes(conn(), g.familia['id'], current_app.cfg):
            return redirect(url_for('familia.consentimento'))
        return f(*a, **kw)
    return w


def operador_obrigatorio(f):
    @functools.wraps(f)
    def w(*a, **kw):
        if 'familia_id' not in session:
            return redirect(url_for('auth.entrar'))
        fam = contas.por_id(conn(), session['familia_id'])
        if not fam or fam['papel'] not in ('operador', 'admin'):
            abort(403)
        g.familia = fam
        return f(*a, **kw)
    return w


def crianca_da_familia(crianca_id):
    c = svc_cri.da_familia(conn(), g.familia['id'], crianca_id)
    if not c:
        abort(404)
    return c


def erro(e):
    flash(str(e), 'danger')
    db.marcar_rollback()
