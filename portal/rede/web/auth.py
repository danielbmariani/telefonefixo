"""auth.py — E1: cadastro, verificacao de e-mail, login, reset, sair."""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, current_app

from ..servicos import contas
from ..servicos.contas import ErroUsuario
from .comum import conn, erro
from .. import db

bp = Blueprint('auth', __name__)


@bp.route('/entrar', methods=['GET', 'POST'])
def entrar():
    if request.method == 'POST':
        try:
            f = contas.login(conn(), request.form.get('email'), request.form.get('senha'), g.ip)
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('entrar.html')
        session.clear()
        session.permanent = True
        session['familia_id'] = f['id']
        session['papel'] = f['papel']
        if f['papel'] in ('operador', 'admin'):
            return redirect(url_for('admin.painel'))
        return redirect(url_for('familia.inicio'))
    return render_template('entrar.html')


@bp.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('auth.entrar'))


@bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if request.method == 'POST':
        try:
            email = contas.iniciar_cadastro(conn(), request.form.get('email'), request.form.get('senha'),
                                            request.form.get('senha2'), request.form.get('nome'), g.ip)
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('cadastrar.html', form=request.form)
        session['cadastro_email'] = email
        flash(f'Enviamos um código de 6 dígitos para {email}.', 'success')
        return redirect(url_for('auth.verificar_email'))
    return render_template('cadastrar.html', form={})


@bp.route('/verificar-email', methods=['GET', 'POST'])
def verificar_email():
    email = session.get('cadastro_email')
    if not email:
        return redirect(url_for('auth.cadastrar'))
    if request.method == 'POST':
        try:
            f = contas.confirmar_codigo(conn(), email, request.form.get('codigo'), g.ip)
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('verificar_email.html', email=email)
        session.clear()
        session.permanent = True
        session['familia_id'] = f['id']
        session['papel'] = f['papel']
        return redirect(url_for('familia.consentimento'))
    return render_template('verificar_email.html', email=email)


@bp.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    email = session.get('cadastro_email')
    if not email:
        return redirect(url_for('auth.cadastrar'))
    try:
        contas.reenviar_codigo(conn(), email, g.ip)
        flash(f'Enviamos um novo código para {email}.', 'success')
    except ErroUsuario as e:
        flash(str(e), 'danger')
    return redirect(url_for('auth.verificar_email'))


@bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        try:
            contas.solicitar_reset(conn(), request.form.get('email'), g.ip)
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('esqueci_senha.html')
        flash('Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.', 'info')
        return redirect(url_for('auth.entrar'))
    return render_template('esqueci_senha.html')


@bp.route('/resetar-senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    if request.method == 'POST':
        try:
            contas.aplicar_reset(conn(), token, request.form.get('senha'), request.form.get('senha2'), g.ip)
        except ErroUsuario as e:
            flash(str(e), 'danger')
            return render_template('resetar_senha.html', token=token)
        flash('Senha redefinida. Faça login.', 'success')
        return redirect(url_for('auth.entrar'))
    return render_template('resetar_senha.html', token=token)
