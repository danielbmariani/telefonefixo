"""contas.py — E1: conta da familia, verificacao de e-mail, consentimento, login, reset, exclusao."""

import re
from datetime import timedelta

from sqlalchemy import select, insert, update, delete, and_

from .. import db, auditoria, seguranca
from ..tempo import agora
from . import textos

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class ErroUsuario(Exception):
    """Mensagem segura para mostrar a familia."""


def _mailer():
    from flask import current_app
    return current_app.mailer


def _cfg():
    """Config da aplicacao. Fora do Flask (AGIs do Asterisk), monta a partir do ambiente (portal.env ja carregado)."""
    try:
        from flask import current_app
        return current_app.cfg
    except RuntimeError:
        from ..config import Config
        return Config()


def validar_email(email):
    e = (email or '').strip().lower()
    if not EMAIL_RE.match(e) or len(e) > 200:
        raise ErroUsuario('E-mail inválido.')
    return e


def validar_senha(senha, senha2=None, email=''):
    if not senha or len(senha) < 8:
        raise ErroUsuario('A senha deve ter pelo menos 8 caracteres.')
    if len(senha) > 128:
        raise ErroUsuario('A senha é longa demais (máximo 128 caracteres).')
    if seguranca.senha_fraca(senha, email):
        raise ErroUsuario('Essa senha é fácil de adivinhar. Use uma frase ou misture palavras, números e sinais.')
    if senha2 is not None and senha != senha2:
        raise ErroUsuario('As senhas não conferem.')
    return senha


def por_email(conn, email):
    return conn.execute(select(db.familias).where(db.familias.c.email == email)).mappings().first()


def por_id(conn, familia_id):
    return conn.execute(select(db.familias).where(db.familias.c.id == familia_id)).mappings().first()


# --- E1 passo 1: iniciar cadastro ---

def iniciar_cadastro(conn, email, senha, senha2, nome, ip, cfg=None, mailer=None):
    cfg = cfg or _cfg()
    mailer = mailer or _mailer()
    email = validar_email(email)
    validar_senha(senha, senha2, email)
    nome = (nome or '').strip()[:80]
    if seguranca.excedeu(f'cadastro:{ip}', 10, 3600):
        auditoria.registrar(conn, 'suspeita_cadastro_massa', 'sistema', None, 'ip', ip)
        raise ErroUsuario('Muitas tentativas deste endereço. Tente mais tarde.')
    seguranca.registrar_tentativa(f'cadastro:{ip}')
    if por_email(conn, email):
        # Nao revelar que existe: segue como se tivesse enviado o codigo; quem e dono do e-mail recebe um aviso.
        auditoria.registrar(conn, 'cadastro_email_ja_existe', 'sistema', None, 'email', seguranca.sha256(email))
        mailer.enviar(email, f'Alguém tentou criar uma conta com este e-mail na {cfg.NOME_REDE}',
                      f'Você já tem conta na {cfg.NOME_REDE}. Se foi você, entre em {cfg.SITE_URL}/entrar ou use '
                      f'"esqueci a senha". Se não foi você, ignore este e-mail: nada foi alterado.')
        return email
    reenvios = conn.execute(select(db.verificacoes_email).where(and_(
        db.verificacoes_email.c.email == email,
        db.verificacoes_email.c.criado_em > agora() - timedelta(hours=1)))).mappings().all()
    if len(reenvios) >= 3:
        raise ErroUsuario('Limite de códigos por hora atingido. Aguarde e tente de novo.')
    codigo = seguranca.codigo_numerico(6)
    conn.execute(insert(db.verificacoes_email).values(
        email=email, senha_hash=seguranca.hash_senha(senha), nome=nome, codigo=codigo,
        expira_em=agora() + timedelta(minutes=cfg.CODIGO_EMAIL_EXPIRA_MIN), criado_em=agora(), ip=ip))
    mailer.enviar(email, f'Seu código de verificação na {cfg.NOME_REDE}',
                  f'Seu código de verificação é: {codigo}\n\nEle expira em {cfg.CODIGO_EMAIL_EXPIRA_MIN} minutos.\n'
                  f'Se você não pediu este código, ignore este e-mail.')
    auditoria.registrar(conn, 'cadastro_iniciado', 'familia', None, 'email', seguranca.sha256(email),
                        detalhes={'reenvio': len(reenvios)})
    return email


def reenviar_codigo(conn, email, ip, cfg=None, mailer=None):
    """Novo codigo para um cadastro em andamento (mesma senha e nome do pedido anterior).
    Limites: 3 codigos por e-mail por hora; o codigo anterior deixa de valer."""
    cfg = cfg or _cfg()
    mailer = mailer or _mailer()
    email = validar_email(email)
    pend = conn.execute(select(db.verificacoes_email).where(and_(
        db.verificacoes_email.c.email == email, db.verificacoes_email.c.usado == False))  # noqa: E712
        .order_by(db.verificacoes_email.c.id.desc())).mappings().first()
    if not pend:
        raise ErroUsuario('Nenhum cadastro em andamento para este e-mail. Comece de novo.')
    reenvios = conn.execute(select(db.verificacoes_email).where(and_(
        db.verificacoes_email.c.email == email,
        db.verificacoes_email.c.criado_em > agora() - timedelta(hours=1)))).mappings().all()
    if len(reenvios) >= 3:
        raise ErroUsuario('Limite de códigos por hora atingido. Aguarde e tente de novo.')
    conn.execute(update(db.verificacoes_email).where(db.verificacoes_email.c.id == pend['id']).values(usado=True))
    codigo = seguranca.codigo_numerico(6)
    conn.execute(insert(db.verificacoes_email).values(
        email=email, senha_hash=pend['senha_hash'], nome=pend['nome'], codigo=codigo,
        expira_em=agora() + timedelta(minutes=cfg.CODIGO_EMAIL_EXPIRA_MIN), criado_em=agora(), ip=ip))
    mailer.enviar(email, f'Seu novo código de verificação na {cfg.NOME_REDE}',
                  f'Seu novo código de verificação é: {codigo}\n\nEle expira em {cfg.CODIGO_EMAIL_EXPIRA_MIN} minutos.\n'
                  f'Se você não pediu este código, ignore este e-mail.')
    auditoria.registrar(conn, 'cadastro_codigo_reenviado', 'familia', None, 'email', seguranca.sha256(email),
                        detalhes={'reenvio': len(reenvios)}, ip=ip)
    return email


# --- E1 passo 2: confirmar codigo ---

def confirmar_codigo(conn, email, codigo, ip):
    email = validar_email(email)
    codigo = (codigo or '').strip()
    pend = conn.execute(select(db.verificacoes_email).where(and_(
        db.verificacoes_email.c.email == email, db.verificacoes_email.c.usado == False))  # noqa: E712
        .order_by(db.verificacoes_email.c.id.desc())).mappings().first()
    if not pend:
        raise ErroUsuario('Código incorreto ou expirado. Comece de novo.')
    if pend['expira_em'] and db_utc(pend['expira_em']) < agora():
        raise ErroUsuario('Código expirado. Comece de novo.')
    if pend['tentativas'] >= 5:
        raise ErroUsuario('Muitas tentativas. Comece de novo.')
    if codigo != pend['codigo']:
        conn.execute(update(db.verificacoes_email).where(db.verificacoes_email.c.id == pend['id'])
                     .values(tentativas=pend['tentativas'] + 1))
        auditoria.registrar(conn, 'codigo_email_incorreto', 'familia', None, 'email', seguranca.sha256(email))
        raise ErroUsuario('Código incorreto.')
    if por_email(conn, email):
        raise ErroUsuario('Este e-mail já tem conta. Faça login.')
    r = conn.execute(insert(db.familias).values(
        email=email, senha_hash=pend['senha_hash'], nome=pend['nome'], papel='familia',
        verificado_em=agora(), criado_em=agora()))
    fid = r.inserted_primary_key[0]
    conn.execute(update(db.verificacoes_email).where(db.verificacoes_email.c.id == pend['id']).values(usado=True))
    auditoria.registrar(conn, 'conta_criada', 'familia', fid, 'familia', fid, ip=ip)
    auditoria.registrar(conn, 'email_verificado', 'familia', fid, 'familia', fid,
                        detalhes={'tentativas': pend['tentativas'] + 1})
    return por_id(conn, fid)


def db_utc(dt):
    from ..tempo import utc
    return utc(dt)


# --- Consentimento (LGPD art. 14; ECA Digital) ---

TIPOS_CONSENTIMENTO = ('termos', 'privacidade', 'crianca')


def consentimentos_pendentes(conn, familia_id, cfg=None):
    cfg = cfg or _cfg()
    versoes = textos.versoes(cfg)
    dados = conn.execute(select(db.consentimentos.c.tipo, db.consentimentos.c.versao)
                         .where(db.consentimentos.c.familia_id == familia_id)).all()
    ok = {(t, v) for t, v in dados}
    return [t for t in TIPOS_CONSENTIMENTO if (t, versoes[t]) not in ok]


def registrar_consentimentos(conn, familia_id, tipos, ip, cfg=None):
    cfg = cfg or _cfg()
    versoes = textos.versoes(cfg)
    for t in tipos:
        if t not in TIPOS_CONSENTIMENTO:
            raise ErroUsuario('Consentimento inválido.')
        conn.execute(insert(db.consentimentos).values(
            familia_id=familia_id, tipo=t, versao=versoes[t], hash_texto=textos.hash_texto(t),
            ts=agora(), ip=ip))
        auditoria.registrar(conn, f'consentimento_{t}', 'familia', familia_id, 'familia', familia_id,
                            detalhes={'versao': versoes[t], 'hash_texto': textos.hash_texto(t)})


# --- Login ---

def login(conn, email, senha, ip):
    if seguranca.excedeu(f'login:{ip}', 5, 900):
        raise ErroUsuario('Muitas tentativas. Aguarde 15 minutos.')
    try:
        email = validar_email(email)
    except ErroUsuario:
        seguranca.registrar_tentativa(f'login:{ip}')
        raise ErroUsuario('E-mail ou senha incorretos.')
    # Limite tambem por conta: forca bruta distribuida por varios IPs contra um e-mail
    if seguranca.excedeu(f'login-email:{email}', 15, 900):
        auditoria.registrar(conn, 'login_bloqueado_por_conta', 'sistema', None, 'email', seguranca.sha256(email), ip=ip)
        raise ErroUsuario('Muitas tentativas. Aguarde 15 minutos.')
    f = por_email(conn, email)
    if not f or not seguranca.verificar_senha(senha or '', f['senha_hash']):
        seguranca.registrar_tentativa(f'login:{ip}')
        seguranca.registrar_tentativa(f'login-email:{email}')
        auditoria.registrar(conn, 'login_falhou', 'familia', None, 'email', seguranca.sha256(email), ip=ip)
        raise ErroUsuario('E-mail ou senha incorretos.')
    if f['suspensa']:
        auditoria.registrar(conn, 'login_conta_suspensa', 'familia', f['id'], 'familia', f['id'], ip=ip)
        raise ErroUsuario('Conta suspensa. Entre em contato com o suporte.')
    auditoria.registrar(conn, 'login_ok', 'familia', f['id'], 'familia', f['id'], ip=ip)
    return f


# --- Reset de senha ---

def solicitar_reset(conn, email, ip, cfg=None, mailer=None):
    cfg = cfg or _cfg()
    mailer = mailer or _mailer()
    if seguranca.excedeu(f'reset:{ip}', 5, 900):
        raise ErroUsuario('Muitas tentativas. Aguarde 15 minutos.')
    seguranca.registrar_tentativa(f'reset:{ip}')
    try:
        email = validar_email(email)
    except ErroUsuario:
        return
    f = por_email(conn, email)
    if f:
        token = seguranca.token_url(32)
        conn.execute(insert(db.password_resets).values(email=email, token_hash=seguranca.sha256(token), criado_em=agora()))
        mailer.enviar(email, f'Redefinir sua senha na {cfg.NOME_REDE}',
                      f'Para redefinir sua senha, abra (válido por 1 hora):\n{cfg.SITE_URL}/resetar-senha/{token}\n\n'
                      f'Se você não pediu isso, ignore.')
        auditoria.registrar(conn, 'reset_solicitado', 'familia', f['id'], 'familia', f['id'], ip=ip)


def aplicar_reset(conn, token, senha, senha2, ip, cfg=None):
    cfg = cfg or _cfg()
    r = conn.execute(select(db.password_resets).where(and_(
        db.password_resets.c.token_hash == seguranca.sha256(token or ''),
        db.password_resets.c.usado == False))).mappings().first()  # noqa: E712
    if not r or db_utc(r['criado_em']) < agora() - timedelta(minutes=cfg.RESET_EXPIRA_MIN):
        raise ErroUsuario('Link inválido ou expirado.')
    validar_senha(senha, senha2, r['email'])
    conn.execute(update(db.familias).where(db.familias.c.email == r['email']).values(senha_hash=seguranca.hash_senha(senha)))
    conn.execute(update(db.password_resets).where(db.password_resets.c.id == r['id']).values(usado=True))
    f = por_email(conn, r['email'])
    auditoria.registrar(conn, 'senha_redefinida', 'familia', f['id'] if f else None, 'familia', f['id'] if f else None, ip=ip)


# --- Operador ---

def criar_operador(conn, email, senha, nome, papel='operador'):
    email = validar_email(email)
    validar_senha(senha)
    r = conn.execute(insert(db.familias).values(email=email, senha_hash=seguranca.hash_senha(senha), nome=nome,
                                                papel=papel, verificado_em=agora(), criado_em=agora()))
    fid = r.inserted_primary_key[0]
    auditoria.registrar(conn, 'operador_criado', 'sistema', None, 'familia', fid, detalhes={'papel': papel})
    return fid


# --- Exclusao de conta (cascata) ---

def excluir_conta(conn, familia_id, confirmacao, ip, cfg=None):
    from . import telefones as svc_tel, criancas as svc_cri
    cfg = cfg or _cfg()
    if (confirmacao or '').strip().upper() != 'EXCLUIR':
        raise ErroUsuario('Digite EXCLUIR para confirmar.')
    f = por_id(conn, familia_id)
    if not f:
        raise ErroUsuario('Conta não encontrada.')
    resumo = {'criancas': [], 'telefones': []}
    for c in svc_cri.listar(conn, familia_id):
        for t in svc_tel.listar_da_crianca(conn, c['id'], incluir_desativados=False):
            svc_tel.desativar(conn, t['id'], 'familia', familia_id, motivo='exclusao_conta', cfg=cfg)
            resumo['telefones'].append(t['mac'])
        svc_cri.desativar(conn, c['id'], 'familia', familia_id)
        resumo['criancas'].append(c['id_rede'])
    # Celulares da familia e historico de ligacoes das criancas removidas
    from . import retencao
    conn.execute(delete(db.familia_telefones).where(db.familia_telefones.c.familia_id == familia_id))
    chamadas = retencao.apagar_chamadas_de(conn, resumo['criancas'])
    # Dados pessoais da conta: e-mail vira hash (retencao minimizada), senha invalida
    conn.execute(update(db.familias).where(db.familias.c.id == familia_id).values(
        email=f'excluida-{familia_id}@invalido', senha_hash='x', nome='', suspensa=True))
    conn.execute(delete(db.password_resets).where(db.password_resets.c.email == f['email']))
    auditoria.registrar(conn, 'conta_excluida', 'familia', familia_id, 'familia', familia_id, ip=ip,
                        detalhes={'apagado': ['email', 'nome', 'senha', 'apelidos', 'amizades', 'horarios', 'celulares',
                                              'ligacoes', 'ramais_asterisk', 'tokens'],
                                  'retido': ['audit_log (IP por 1 ano)', 'consentimentos (prova do aceite)',
                                             'device_state_history, prov_log, gdms_log (180 dias)', 'totais por dia sem identificacao'],
                                  'ligacoes_apagadas': chamadas,
                                  'email_hash': seguranca.sha256(f['email']), **resumo})
    return resumo
