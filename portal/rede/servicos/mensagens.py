"""mensagens.py — Formulário de contato do site: cada mensagem vira um caso no painel (tipo 'mensagem') e um
e-mail para o endereço de avisos. A resposta à família continua sendo por e-mail; o caso é fechado no painel."""

from sqlalchemy import insert

from .. import db, auditoria, seguranca
from ..tempo import agora
from .contas import ErroUsuario

LIMITE_POR_IP_HORA = 5


def receber(conn, cfg, mailer, nome, email, mensagem, ip, familia=None):
    nome, email, mensagem = (nome or '').strip(), (email or '').strip().lower(), (mensagem or '').strip()
    if not 2 <= len(nome) <= 80:
        raise ErroUsuario('Diga seu nome.')
    if '@' not in email or '.' not in email.split('@')[-1] or len(email) > 120:
        raise ErroUsuario('Digite um e-mail válido, para podermos responder.')
    if len(mensagem) < 10:
        raise ErroUsuario('Conte um pouco mais: o que aconteceu, com qual criança e quando.')
    if len(mensagem) > 2000:
        raise ErroUsuario('A mensagem pode ter até 2000 caracteres.')
    chave = f'contato:{ip}'
    if seguranca.excedeu(chave, LIMITE_POR_IP_HORA, 3600):
        auditoria.registrar(conn, 'mensagem_bloqueada_rate_limit', 'familia', None, ip=ip)
        raise ErroUsuario('Muitas mensagens seguidas. Aguarde uma hora ou escreva para o e-mail de contato.')
    seguranca.registrar_tentativa(chave)
    resumo = mensagem if len(mensagem) <= 200 else mensagem[:200] + '…'
    cid = conn.execute(insert(db.casos).values(
        tipo='mensagem', gravidade='media', familia_id=familia['id'] if familia else None, estado='aberto', criado_em=agora(),
        descricao=f'Mensagem pelo site de {nome} <{email}>: {resumo}',
        detalhes={'nome': nome, 'email': email, 'mensagem': mensagem, 'conta': bool(familia)})).inserted_primary_key[0]
    auditoria.registrar(conn, 'mensagem_recebida', 'familia', familia['id'] if familia else None,
                        'caso', cid, ip=ip, detalhes={'tamanho': len(mensagem)})
    if mailer is not None and cfg.ALERTA_EMAIL:
        mailer.enviar(cfg.ALERTA_EMAIL, f'Mensagem pelo site de {nome} (caso #{cid})',
                      f'De: {nome} <{email}>{" (tem conta no site)" if familia else ""}\n\n{mensagem}\n\n'
                      f'Responda para {email}. Depois, resolva o caso #{cid} em {cfg.SITE_URL}/ong/casos')
    return cid
