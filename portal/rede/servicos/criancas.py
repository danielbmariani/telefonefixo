"""criancas.py — E2: apelido + ID + ramal (ps_endpoints/ps_auths/ps_aors) na mesma transacao."""

import re

from sqlalchemy import select, insert, update, delete, and_

from .. import db, auditoria, voz, seguranca, ids
from ..tempo import agora
from .contas import ErroUsuario

CONTEXTO_DIALPLAN = 'telefones-criancas'


def listar(conn, familia_id, incluir_inativas=False):
    q = select(db.criancas).where(db.criancas.c.familia_id == familia_id)
    if not incluir_inativas:
        q = q.where(db.criancas.c.ativa == True)  # noqa: E712
    return conn.execute(q.order_by(db.criancas.c.id)).mappings().all()


def por_id(conn, crianca_id):
    return conn.execute(select(db.criancas).where(db.criancas.c.id == crianca_id)).mappings().first()


def por_id_rede(conn, id_rede):
    return conn.execute(select(db.criancas).where(db.criancas.c.id_rede == id_rede)).mappings().first()


def da_familia(conn, familia_id, crianca_id):
    c = por_id(conn, crianca_id)
    if not c or c['familia_id'] != familia_id or not c['ativa']:
        return None
    return c


def _id_existe(conn):
    def f(candidato):
        return conn.execute(select(db.criancas.c.id).where(db.criancas.c.id_rede == candidato)).first() is not None
    return f


NOME_MAX = 30
_NOME_RE = re.compile(r"^[^\W\d_][^\W\d_]*(?:[ '\-][^\W\d_]+)*$")


def validar_nome(texto):
    """Nome falado (opcional): 'Laura', 'Maria Clara', 'Zé'. So letras, espacos, hifen e apostrofo, ate 30 caracteres.
    Vazio -> None. Invalido -> ErroUsuario."""
    n = re.sub(r'\s+', ' ', (texto or '')).strip()
    if not n:
        return None
    if len(n) > NOME_MAX or not _NOME_RE.match(n):
        raise ErroUsuario('O nome é só para a voz falar: use letras e espaços, até 30 caracteres, sem números.')
    return n


def exibicao(crianca):
    """Como a familia ve a crianca: 'Laura (laura01)' ou so 'laura01'."""
    nome = crianca.get('nome') if hasattr(crianca, 'get') else crianca['nome']
    return f"{nome} ({crianca['apelido']})" if nome else crianca['apelido']


def nome_falado(crianca):
    return crianca['nome'] or crianca['apelido']


def definir_nome(conn, crianca, nome, cfg, familia_id=None):
    """Troca o nome falado (ou apaga, com vazio). Regera o audio na hora; erro de voz nao derruba a troca."""
    n = validar_nome(nome)
    antes = crianca['nome']
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca['id']).values(nome=n))
    auditoria.registrar(conn, 'crianca_nome_alterado', 'familia', familia_id or crianca['familia_id'], 'crianca', crianca['id'],
                        detalhes={'tinha': bool(antes), 'tem': bool(n)})
    try:
        if n:
            voz.gerar_nome(cfg, crianca['id_rede'], n)
        else:
            voz.apagar_nome(cfg, crianca['id_rede'])
    except Exception as e:
        auditoria.registrar(conn, 'voz_falhou', 'sistema', None, 'crianca', crianca['id'], detalhes={'erro': str(e)[:200]})
    return n


def criar(conn, familia_id, apelido, cfg, ator_id=None, nome=None):
    nome = validar_nome(nome)
    try:
        apelido = ids.validar_nick(apelido)
    except ValueError as e:
        auditoria.registrar(conn, 'apelido_rejeitado', 'familia', familia_id, 'familia', familia_id,
                            detalhes={'motivo': str(e)})
        raise ErroUsuario(str(e))
    if conn.execute(select(db.criancas.c.id).where(db.criancas.c.apelido == apelido)).first():
        auditoria.registrar(conn, 'apelido_rejeitado', 'familia', familia_id, 'familia', familia_id,
                            detalhes={'motivo': 'ja_existe'})
        raise ErroUsuario('Esse apelido já está em uso. Escolha outro.')
    if len(listar(conn, familia_id)) >= 6:
        raise ErroUsuario('Limite de crianças por conta atingido.')
    id_rede = ids.gerar_id(_id_existe(conn))
    senha = seguranca.senha_sip()
    r = conn.execute(insert(db.criancas).values(familia_id=familia_id, apelido=apelido, id_rede=id_rede, nome=nome,
                                                senha_sip=senha, criado_em=agora(), ativa=True))
    cid = r.inserted_primary_key[0]
    _criar_ramal(conn, id_rede, senha, apelido, cfg.SIP_CIFRAGEM)
    auditoria.registrar(conn, 'crianca_criada', 'familia', ator_id or familia_id, 'crianca', cid,
                        detalhes={'id_rede': id_rede, 'apelido': apelido})
    auditoria.registrar(conn, 'ramal_criado', 'sistema', None, 'crianca', cid,
                        detalhes={'id_rede': id_rede, 'senha_sip_sha256': seguranca.sha256(senha)})
    try:  # apelido (e nome) falados para a chamada em grupo e o menu de entrada; nunca derruba o cadastro
        voz.gerar_apelido(cfg, id_rede, apelido)
        if nome:
            voz.gerar_nome(cfg, id_rede, nome)
    except Exception as e:
        auditoria.registrar(conn, 'voz_falhou', 'sistema', None, 'crianca', cid, detalhes={'erro': str(e)[:200]})
    return por_id(conn, cid)


# Cifragem entre o telefone e a central, do lado do Asterisk (o lado do aparelho e grandstream_xml.pvalues_linha).
# Com TLS o ramal fica sem transporte fixo: o Asterisk responde pela conexao em que o telefone se registrou.
# transicao aceita ligacao sem SRTP (aparelho que ainda nao pegou a configuracao nova); exigida recusa.
CIFRAGENS = {
    'nenhuma': {'transport': 'transport-tcp', 'media_encryption': 'no', 'media_encryption_optimistic': 'no'},
    'transicao': {'transport': None, 'media_encryption': 'sdes', 'media_encryption_optimistic': 'yes'},
    'exigida': {'transport': None, 'media_encryption': 'sdes', 'media_encryption_optimistic': 'no'},
}


def cifragem(conn, id_rede):
    """Modo atual do ramal, lido do que o Asterisk usa: 'nenhuma', 'transicao' ou 'exigida'."""
    e = conn.execute(select(db.ps_endpoints.c.media_encryption, db.ps_endpoints.c.media_encryption_optimistic)
                     .where(db.ps_endpoints.c.id == id_rede)).first()
    if not e or e[0] != 'sdes':
        return 'nenhuma'
    return 'transicao' if e[1] == 'yes' else 'exigida'


def nome_certificado(cfg, id_rede):
    """Nome que o aparelho desta linha confere no certificado da central, ou None se a linha nao confere
    (config SIP_CERT_NOME e SIP_CERT_LINHAS)."""
    linhas = {x.strip() for x in (cfg.SIP_CERT_LINHAS or '').split(',') if x.strip()}
    return cfg.SIP_CERT_NOME if cfg.SIP_CERT_NOME and ('todas' in linhas or id_rede in linhas) else None


def definir_cifragem(conn, crianca, modo, ator_tipo='sistema', ator_id=None):
    """Muda a cifragem do ramal de uma crianca. O aparelho so acompanha quando recebe a configuracao nova
    (telefones.aplicar_cifragem cuida disso). Retorna o modo anterior."""
    if modo not in CIFRAGENS:
        raise ValueError(f'cifragem deve ser uma de {tuple(CIFRAGENS)}')
    antes = cifragem(conn, crianca['id_rede'])
    conn.execute(update(db.ps_endpoints).where(db.ps_endpoints.c.id == crianca['id_rede']).values(**CIFRAGENS[modo]))
    auditoria.registrar(conn, 'cifragem_alterada', ator_tipo, ator_id, 'crianca', crianca['id'],
                        detalhes={'de': antes, 'para': modo})
    return antes


def _criar_ramal(conn, id_rede, senha, apelido, modo='nenhuma'):
    conn.execute(insert(db.ps_endpoints).values(
        id=id_rede, aors=id_rede, auth=id_rede, context=CONTEXTO_DIALPLAN, **CIFRAGENS[modo],
        disallow='all', allow='g722,ulaw,alaw', direct_media='no', rtp_symmetric='yes', force_rport='yes',
        rewrite_contact='yes', callerid=f'{apelido} <{id_rede}>', dtmf_mode='rfc4733'))
    conn.execute(insert(db.ps_auths).values(id=id_rede, auth_type='userpass', username=id_rede, password=senha))
    conn.execute(insert(db.ps_aors).values(id=id_rede, max_contacts=1, remove_existing='yes',
                                          default_expiration=120, qualify_frequency=60))


def rotacionar_senha_sip(conn, crianca_id, ator_tipo, ator_id, motivo):
    c = por_id(conn, crianca_id)
    nova = seguranca.senha_sip()
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(senha_sip=nova))
    conn.execute(update(db.ps_auths).where(db.ps_auths.c.id == c['id_rede']).values(password=nova))
    auditoria.registrar(conn, 'senha_sip_rotacionada', ator_tipo, ator_id, 'crianca', crianca_id,
                        detalhes={'motivo': motivo, 'senha_sip_sha256': seguranca.sha256(nova)})
    return nova


def desativar(conn, crianca_id, ator_tipo, ator_id):
    c = por_id(conn, crianca_id)
    if not c:
        return
    for t in (db.ps_endpoints, db.ps_auths, db.ps_aors):
        conn.execute(delete(t).where(t.c.id == c['id_rede']))
    conn.execute(delete(db.amizades).where((db.amizades.c.de_crianca_id == crianca_id) |
                                           (db.amizades.c.para_crianca_id == crianca_id)))
    conn.execute(delete(db.horarios).where(db.horarios.c.crianca_id == crianca_id))
    conn.execute(update(db.criancas).where(db.criancas.c.id == crianca_id).values(
        ativa=False, desativada_em=agora(), apelido=f'removido-{crianca_id}', nome=None, senha_sip='x'))
    auditoria.registrar(conn, 'crianca_desativada', ator_tipo, ator_id, 'crianca', crianca_id,
                        detalhes={'id_rede': c['id_rede']})


def ramal_consistente(conn, crianca):
    """Para a reconciliacao: as tres linhas ps_* existem para a crianca ativa?"""
    idr = crianca['id_rede']
    e = conn.execute(select(db.ps_endpoints.c.id).where(db.ps_endpoints.c.id == idr)).first()
    a = conn.execute(select(db.ps_auths.c.id).where(db.ps_auths.c.id == idr)).first()
    o = conn.execute(select(db.ps_aors.c.id).where(db.ps_aors.c.id == idr)).first()
    return bool(e and a and o)


def fuso_da_crianca(conn, crianca):
    """Fuso da casa (familias.fuso, nome IANA) ou None = padrao. Vale para o relogio do telefone e os horarios."""
    if not crianca:
        return None
    return conn.execute(select(db.familias.c.fuso).where(db.familias.c.id == crianca['familia_id'])).scalar()
