"""turmas.py — Turmas: grupo de criancas com codigo de convite. Quem cria administra e aceita quem entra;
ao ser aceita, a crianca pede amizade a todos os membros (cada familia ainda aceita um a um). Doc 12, item 1."""

import secrets
from datetime import timedelta

from sqlalchemy import select, insert, update, and_, func

from .. import db, auditoria
from ..tempo import agora
from .contas import ErroUsuario
from . import criancas as svc_cri, amizades as svc_ami

ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # sem I, O, 0, 1
NOME_MAX = 40
MAX_TURMAS_POR_FAMILIA = 3
MAX_TURMAS_POR_CRIANCA = 5
MAX_ENTRADAS_DIA = 5


def _codigo(conn):
    for _ in range(50):
        c = ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(6))
        if not conn.execute(select(db.turmas.c.id).where(db.turmas.c.codigo == c)).first():
            return c
    raise RuntimeError('nao consegui gerar codigo de turma')


def formatar_codigo(c):
    return f'{c[:3]} {c[3:]}'


def limpar_nome(nome):
    n = ' '.join((nome or '').split())
    if len(n) < 3 or len(n) > NOME_MAX:
        raise ErroUsuario(f'O nome da turma deve ter de 3 a {NOME_MAX} caracteres.')
    return n


def por_id(conn, turma_id):
    return conn.execute(select(db.turmas).where(db.turmas.c.id == turma_id)).mappings().first()


def criar(conn, familia_id, crianca, nome):
    nome = limpar_nome(nome)
    n = conn.execute(select(func.count()).select_from(db.turmas).where(and_(
        db.turmas.c.familia_id == familia_id, db.turmas.c.ativa == True))).scalar()  # noqa: E712
    if n >= MAX_TURMAS_POR_FAMILIA:
        raise ErroUsuario(f'Uma família pode administrar no máximo {MAX_TURMAS_POR_FAMILIA} turmas.')
    tid = conn.execute(insert(db.turmas).values(nome=nome, codigo=_codigo(conn), familia_id=familia_id,
                                                ativa=True, criado_em=agora())).inserted_primary_key[0]
    conn.execute(insert(db.turma_membros).values(turma_id=tid, crianca_id=crianca['id'], estado='aceita',
                                                 criado_em=agora(), respondido_em=agora()))
    auditoria.registrar(conn, 'turma_criada', 'familia', familia_id, 'turma', tid, detalhes={'crianca': crianca['id']})
    return por_id(conn, tid)


def entrar(conn, familia_id, crianca, codigo):
    """Pedido de entrada pelo codigo. Fica pendente ate o administrador aceitar."""
    c = ''.join(ch for ch in (codigo or '').upper() if ch.isalnum())
    hoje = conn.execute(select(func.count()).select_from(db.turma_membros).join(db.criancas, db.criancas.c.id == db.turma_membros.c.crianca_id)
                        .where(and_(db.criancas.c.familia_id == familia_id,
                                    db.turma_membros.c.criado_em > agora() - timedelta(days=1)))).scalar()
    if hoje >= MAX_ENTRADAS_DIA:
        auditoria.registrar(conn, 'suspeita_codigos_turma', 'sistema', None, 'familia', familia_id)
        raise ErroUsuario('Muitas tentativas hoje. Tente amanhã.')
    t = conn.execute(select(db.turmas).where(and_(db.turmas.c.codigo == c, db.turmas.c.ativa == True))).mappings().first()  # noqa: E712
    if not t:
        auditoria.registrar(conn, 'codigo_turma_invalido', 'familia', familia_id, 'crianca', crianca['id'])
        raise ErroUsuario('Código de turma não encontrado. Confira com quem criou a turma.')
    quantas = conn.execute(select(func.count()).select_from(db.turma_membros).where(and_(
        db.turma_membros.c.crianca_id == crianca['id'], db.turma_membros.c.estado.in_(('pendente', 'aceita'))))).scalar()
    if quantas >= MAX_TURMAS_POR_CRIANCA:
        raise ErroUsuario(f'Uma criança pode estar em no máximo {MAX_TURMAS_POR_CRIANCA} turmas.')
    m = conn.execute(select(db.turma_membros).where(and_(db.turma_membros.c.turma_id == t['id'],
                                                         db.turma_membros.c.crianca_id == crianca['id']))).mappings().first()
    if m and m['estado'] == 'aceita':
        raise ErroUsuario(f'{crianca["apelido"]} já está na turma {t["nome"]}.')
    if m and m['estado'] == 'pendente':
        raise ErroUsuario('Pedido já enviado. Aguarde quem administra a turma aceitar.')
    if m:
        conn.execute(update(db.turma_membros).where(db.turma_membros.c.id == m['id'])
                     .values(estado='pendente', criado_em=agora(), respondido_em=None))
        mid = m['id']
    else:
        mid = conn.execute(insert(db.turma_membros).values(turma_id=t['id'], crianca_id=crianca['id'], estado='pendente',
                                                           criado_em=agora())).inserted_primary_key[0]
    auditoria.registrar(conn, 'turma_entrada_pedida', 'familia', familia_id, 'turma', t['id'],
                        detalhes={'crianca': crianca['id'], 'membro': mid})
    _avisar_admin(conn, t, crianca)
    return t


def _avisar_admin(conn, turma, crianca):
    try:
        from flask import current_app
        mailer, cfg = current_app.mailer, current_app.cfg
    except RuntimeError:
        return
    fam = conn.execute(select(db.familias).where(db.familias.c.id == turma['familia_id'])).mappings().first()
    if fam and '@' in fam['email'] and not fam['email'].startswith('excluida-'):
        mailer.enviar(fam['email'], f'{crianca["apelido"]} quer entrar na turma {turma["nome"]}',
                      f'A família de {crianca["apelido"]} pediu para entrar na turma {turma["nome"]}.\n\n'
                      f'Aceite ou recuse em {cfg.SITE_URL}/turma/{turma["id"]}\n\n'
                      f'Se você não reconhece essa criança, basta recusar.')


def responder(conn, membro_id, familia_id, acao, cfg):
    """So a familia administradora. Ao aceitar, a crianca nova pede amizade a cada membro aceito."""
    m = conn.execute(select(db.turma_membros).where(db.turma_membros.c.id == membro_id)).mappings().first()
    t = por_id(conn, m['turma_id']) if m else None
    if not m or not t or t['familia_id'] != familia_id or m['estado'] != 'pendente':
        raise ErroUsuario('Pedido não encontrado.')
    novo = 'aceita' if acao == 'aceitar' else 'recusada'
    conn.execute(update(db.turma_membros).where(db.turma_membros.c.id == membro_id)
                 .values(estado=novo, respondido_em=agora()))
    auditoria.registrar(conn, f'turma_entrada_{novo}', 'familia', familia_id, 'turma', t['id'], detalhes={'membro': membro_id})
    pedidos = 0
    if novo == 'aceita':
        cr = svc_cri.por_id(conn, m['crianca_id'])
        for outro in membros(conn, t['id']):
            if outro['crianca_id'] == cr['id'] or outro['estado'] != 'aceita':
                continue
            try:
                r = svc_ami.pedir(conn, cr, outro['id_rede'], cr['familia_id'], cfg,
                                  mensagem=f'da turma {t["nome"]}', sem_limites=True)
                pedidos += 1 if r is not None else 0
            except ErroUsuario:
                pass        # ja amigos, ja pedido, etc.
        auditoria.registrar(conn, 'turma_pedidos_de_amizade', 'sistema', 'turmas', 'crianca', cr['id'],
                            detalhes={'turma': t['id'], 'pedidos': pedidos})
    return novo, pedidos


def sair(conn, turma_id, crianca, familia_id):
    conn.execute(update(db.turma_membros).where(and_(db.turma_membros.c.turma_id == turma_id,
                                                     db.turma_membros.c.crianca_id == crianca['id']))
                 .values(estado='saiu', respondido_em=agora()))
    auditoria.registrar(conn, 'turma_saida', 'familia', familia_id, 'turma', turma_id, detalhes={'crianca': crianca['id']})


def membros(conn, turma_id):
    rows = conn.execute(select(db.turma_membros, db.criancas.c.apelido, db.criancas.c.id_rede, db.criancas.c.familia_id)
                        .join(db.criancas, db.criancas.c.id == db.turma_membros.c.crianca_id)
                        .where(db.turma_membros.c.turma_id == turma_id)
                        .order_by(db.turma_membros.c.criado_em)).mappings().all()
    return [dict(r) for r in rows]


def das_criancas(conn, crianca_id):
    """Turmas desta crianca (pendentes e aceitas) com contagem de membros."""
    rows = conn.execute(select(db.turmas, db.turma_membros.c.estado.label('meu_estado'), db.turma_membros.c.id.label('membro_id'))
                        .join(db.turma_membros, db.turma_membros.c.turma_id == db.turmas.c.id)
                        .where(and_(db.turma_membros.c.crianca_id == crianca_id, db.turmas.c.ativa == True,  # noqa: E712
                                    db.turma_membros.c.estado.in_(('pendente', 'aceita'))))
                        .order_by(db.turmas.c.criado_em)).mappings().all()
    out = []
    for t in rows:
        n = conn.execute(select(func.count()).select_from(db.turma_membros).where(and_(
            db.turma_membros.c.turma_id == t['id'], db.turma_membros.c.estado == 'aceita'))).scalar()
        pend = conn.execute(select(func.count()).select_from(db.turma_membros).where(and_(
            db.turma_membros.c.turma_id == t['id'], db.turma_membros.c.estado == 'pendente'))).scalar()
        out.append(dict(t, membros=n, pendentes=pend, codigo_fmt=formatar_codigo(t['codigo'])))
    return out


def visao(conn, turma, crianca):
    """Membros da turma com a relacao de amizade em relacao a esta crianca."""
    lst = svc_ami.listar(conn, crianca['id'])
    amigos = {a['id_rede'] for a in lst['amigos']}
    enviados = {a['id_rede'] for a in lst['enviados']}
    recebidos = {a['id_rede']: a['amizade_id'] for a in lst['recebidos']}
    out = []
    for m in membros(conn, turma['id']):
        if m['estado'] not in ('aceita', 'pendente'):
            continue
        rel = 'eu' if m['crianca_id'] == crianca['id'] else (
            'amigo' if m['id_rede'] in amigos else 'pedido_enviado' if m['id_rede'] in enviados
            else 'pedido_recebido' if m['id_rede'] in recebidos else 'nada')
        out.append(dict(m, relacao=rel, amizade_id=recebidos.get(m['id_rede'])))
    return out
