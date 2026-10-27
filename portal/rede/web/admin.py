"""admin.py — painel da ONG: funil, casos, tarefas, telefones, linha do tempo, auditoria (consulta registrada)."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, abort
from sqlalchemy import select, update, and_, or_, desc

from .. import db, auditoria
from ..servicos import reconciliacao, gdms_fila, telefones as svc_tel, criancas as svc_cri
from ..tempo import agora
from .comum import conn, operador_obrigatorio

bp = Blueprint('admin', __name__, url_prefix='/ong')


@bp.route('/')
@operador_obrigatorio
def painel():
    c = conn()
    casos_abertos = c.execute(select(db.casos).where(db.casos.c.estado == 'aberto').order_by(desc(db.casos.c.id)).limit(20)).mappings().all()
    tarefas_abertas = c.execute(select(db.tarefas).where(db.tarefas.c.estado == 'aberta').order_by(db.tarefas.c.id)).mappings().all()
    ultima_rec = c.execute(select(db.audit_log).where(db.audit_log.c.acao == 'reconciliacao_executada')
                           .order_by(desc(db.audit_log.c.id)).limit(1)).mappings().first()
    return render_template('ong/painel.html', funil=reconciliacao.funil(c), por_estado=svc_tel.contar_por_estado(c),
                           casos=casos_abertos, tarefas=tarefas_abertas, ultima_rec=ultima_rec)


@bp.route('/casos', methods=['GET', 'POST'])
@operador_obrigatorio
def casos():
    c = conn()
    if request.method == 'POST':
        cid = request.form.get('caso_id', type=int)
        motivo = (request.form.get('motivo') or '').strip()
        if not motivo:
            flash('Motivo obrigatório.', 'danger')
        else:
            c.execute(update(db.casos).where(and_(db.casos.c.id == cid, db.casos.c.estado == 'aberto'))
                      .values(estado='resolvido', resolvido_em=agora(), resolvido_por=g.familia['email'], motivo=motivo))
            auditoria.registrar(c, 'caso_resolvido', 'operador', g.familia['email'], 'caso', cid, detalhes={'motivo': motivo})
            flash('Caso resolvido.', 'success')
        return redirect(url_for('admin.casos'))
    estado = request.args.get('estado', 'aberto')
    q = select(db.casos).order_by(desc(db.casos.c.id)).limit(200)
    if estado != 'todos':
        q = q.where(db.casos.c.estado == estado)
    return render_template('ong/casos.html', casos=c.execute(q).mappings().all(), estado=estado)


@bp.route('/tarefas', methods=['GET', 'POST'])
@operador_obrigatorio
def tarefas():
    c = conn()
    if request.method == 'POST':
        tid = request.form.get('tarefa_id', type=int)
        try:
            gdms_fila.concluir_tarefa(c, tid, g.familia['email'], request.form.get('motivo'), current_app.cfg)
            flash('Tarefa concluída.', 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('admin.tarefas'))
    rows = c.execute(select(db.tarefas).order_by(db.tarefas.c.estado, desc(db.tarefas.c.id)).limit(200)).mappings().all()
    return render_template('ong/tarefas.html', tarefas=rows)


@bp.route('/telefones')
@operador_obrigatorio
def telefones():
    c = conn()
    busca = (request.args.get('q') or '').strip().upper().replace(':', '').replace('-', '')
    q = select(db.telefones, db.criancas.c.id_rede, db.criancas.c.apelido).join(db.criancas, db.criancas.c.id == db.telefones.c.crianca_id)
    if busca:
        q = q.where(or_(db.telefones.c.mac.like(f'%{busca}%'), db.criancas.c.id_rede == busca))
    rows = c.execute(q.order_by(desc(db.telefones.c.id)).limit(200)).mappings().all()
    if busca:
        auditoria.registrar(c, 'telefones_pesquisados', 'operador', g.familia['email'], detalhes={'q': busca, 'n': len(rows)})
    return render_template('ong/telefones.html', rows=rows, q=busca)


@bp.route('/telefone/<int:telefone_id>')
@operador_obrigatorio
def linha_tempo(telefone_id):
    c = conn()
    tel = svc_tel.por_id(c, telefone_id)
    if not tel:
        abort(404)
    cr = svc_cri.por_id(c, tel['crianca_id'])
    eventos = auditoria.linha_do_tempo(c, telefone_id=telefone_id, crianca_id=tel['crianca_id'])
    auditoria.registrar(c, 'auditoria_consultada', 'operador', g.familia['email'], 'telefone', telefone_id,
                        detalhes={'tipo': 'linha_do_tempo', 'eventos': len(eventos)})
    return render_template('ong/linha_tempo.html', tel=tel, crianca=cr, eventos=eventos)


@bp.route('/auditoria')
@operador_obrigatorio
def auditoria_view():
    c = conn()
    f = {k: (request.args.get(k) or None) for k in ('acao', 'objeto_tipo', 'objeto_id', 'request_id')}
    linhas = []
    if any(f.values()):
        linhas = auditoria.consultar(c, g.familia['email'], acao=f['acao'], objeto_tipo=f['objeto_tipo'],
                                     objeto_id=f['objeto_id'], request_id_filtro=f['request_id'])
    return render_template('ong/auditoria.html', linhas=linhas, f=f)
