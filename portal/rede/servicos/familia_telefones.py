"""
familia_telefones.py — Celulares da familia (doc 08 item 6c, bancada B23).

A crianca disca 9 + o proprio ID e a central liga, pelo tronco da operadora, para o celular 1 da
familia; 8 + ID liga para o celular 2 (decisao do Daniel em 27/10: um jeito de discar para cada celular,
no maximo dois). Quando um desses celulares liga para o numero da rede, a central
reconhece o numero e faz tocar o telefone das criancas daquela familia. Numero desconhecido nao toca.

Numeros guardados so com digitos, no formato nacional: DDD + numero (10 ou 11 digitos).
"""

import re

from sqlalchemy import select, insert, update, and_

from .. import db, auditoria
from ..tempo import agora
from . import criancas as svc_cri, telefones as svc_tel, horarios
from .contas import ErroUsuario

MAX_POR_FAMILIA = 2
PREFIXOS = {1: '9', 2: '8'}   # posicao -> digito que a crianca disca antes do proprio ID
TRONCO_ENDPOINT = 'nvoip'          # nome do endpoint PJSIP do tronco (deploy/tronco.sh)
ESTADOS_TOCAM = ('registrado', 'ativo')
APELIDO_MAX = 20


def normalizar(numero):
    """'+55 (11) 98765-4321' -> '11987654321'. Levanta ErroUsuario se nao for um numero brasileiro valido."""
    d = re.sub(r'\D', '', numero or '')
    if d.startswith('55') and len(d) in (12, 13):
        d = d[2:]
    if d.startswith('0') and len(d) in (11, 12):
        d = d[1:]
    if len(d) not in (10, 11):
        raise ErroUsuario('Digite o número com DDD, por exemplo 11 98765 4321.')
    if not ('11' <= d[:2] <= '99'):
        raise ErroUsuario('DDD inválido.')
    if len(d) == 11 and d[2] != '9':
        raise ErroUsuario('Celular com 9 dígitos começa com 9 depois do DDD.')
    return d


def formatar(numero):
    d = numero or ''
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return d


def limpar_apelido(texto):
    t = re.sub(r'\s+', ' ', (texto or '')).strip()
    return t[:APELIDO_MAX]


def listar(conn, familia_id, so_ativos=True):
    cond = db.familia_telefones.c.familia_id == familia_id
    if so_ativos:
        cond = and_(cond, db.familia_telefones.c.ativo.is_(True))
    return conn.execute(select(db.familia_telefones).where(cond)
                        .order_by(db.familia_telefones.c.posicao, db.familia_telefones.c.id)).mappings().all()


def por_posicao(conn, familia_id, posicao):
    return next((t for t in listar(conn, familia_id) if t['posicao'] == posicao), None)


def trocar_ordem(conn, familia_id):
    """Celular 1 vira 2 e vice-versa."""
    ativos = listar(conn, familia_id)
    if len(ativos) < 2:
        raise ErroUsuario('Só dá para trocar a ordem com dois celulares cadastrados.')
    for t, nova in zip(ativos[:2], (2, 1)):
        conn.execute(update(db.familia_telefones).where(db.familia_telefones.c.id == t['id']).values(posicao=nova))
    auditoria.registrar(conn, 'familia_telefones_ordem_trocada', 'familia', familia_id, 'familia', familia_id)


def adicionar(conn, familia_id, numero, apelido):
    n = normalizar(numero)
    ativos = listar(conn, familia_id)
    if any(t['numero'] == n for t in ativos):
        raise ErroUsuario('Esse número já está cadastrado.')
    if len(ativos) >= MAX_POR_FAMILIA:
        raise ErroUsuario(f'No máximo {MAX_POR_FAMILIA} números por família. Remova um para adicionar outro.')
    posicao = min(set(PREFIXOS) - {t['posicao'] for t in ativos})   # primeira posicao livre
    antigo = conn.execute(select(db.familia_telefones).where(and_(db.familia_telefones.c.familia_id == familia_id,
                                                                  db.familia_telefones.c.numero == n))).mappings().first()
    if antigo:
        conn.execute(update(db.familia_telefones).where(db.familia_telefones.c.id == antigo['id'])
                     .values(ativo=True, apelido=limpar_apelido(apelido), criado_em=agora(), posicao=posicao))
        novo_id = antigo['id']
    else:
        novo_id = conn.execute(insert(db.familia_telefones).values(
            familia_id=familia_id, numero=n, apelido=limpar_apelido(apelido), ativo=True, criado_em=agora(),
            posicao=posicao)).inserted_primary_key[0]
    auditoria.registrar(conn, 'familia_telefone_adicionado', 'familia', familia_id, 'familia_telefone', novo_id,
                        {'numero': n[:2] + '*****' + n[-4:]})
    return n


def remover(conn, familia_id, telefone_id):
    r = conn.execute(update(db.familia_telefones).where(and_(db.familia_telefones.c.id == telefone_id,
                                                              db.familia_telefones.c.familia_id == familia_id))
                     .values(ativo=False, posicao=None))
    if r.rowcount:
        auditoria.registrar(conn, 'familia_telefone_removido', 'familia', familia_id, 'familia_telefone', telefone_id)
    return bool(r.rowcount)


def familia_por_numero(conn, numero):
    """Numero (ja normalizado) -> linha de familia_telefones ativa, ou None. Ultimos 10 digitos tambem
    valem: operadoras entregam o identificador com ou sem o nono digito."""
    candidatos = {numero}
    if len(numero) == 11 and numero[2] == '9':
        candidatos.add(numero[:2] + numero[3:])
    elif len(numero) == 10:
        candidatos.add(numero[:2] + '9' + numero[2:])
    rows = conn.execute(select(db.familia_telefones).where(and_(db.familia_telefones.c.numero.in_(list(candidatos)),
                                                                db.familia_telefones.c.ativo.is_(True)))
                        .order_by(db.familia_telefones.c.id)).mappings().all()
    exatos = [r for r in rows if r['numero'] == numero]
    return (exatos or rows or [None])[0]


def numeros_da_crianca(conn, crianca):
    return [t['numero'] for t in listar(conn, crianca['familia_id'])]


def numero_por_prefixo(conn, crianca, prefixo):
    """'9' -> numero do celular 1, '8' -> celular 2, ou None."""
    pos = next((p for p, d in PREFIXOS.items() if d == prefixo), None)
    t = por_posicao(conn, crianca['familia_id'], pos) if pos else None
    return t['numero'] if t else None


def dial_saida(numero):
    return f'PJSIP/{numero}@{TRONCO_ENDPOINT}'


def numero_do_identificador(*candidatos):
    """Primeiro candidato que vira um numero nacional de 10/11 digitos, ou ''. A Nvoip manda o numero
    do chamador no display name do From (From: "11987654321" <sip:15XXXXXXX@...>), entao o AGI passa
    CALLERID(num), CALLERID(name) e os cabecalhos P-Asserted-Identity / Remote-Party-ID."""
    for c in candidatos:
        if not c:
            continue
        m = re.search(r'sip:\+?(\d+)@', c)
        d = m.group(1) if m else re.sub(r'\D', '', c)
        if d.startswith('55') and len(d) in (12, 13):
            d = d[2:]
        if d.startswith('0') and len(d) in (11, 12):
            d = d[1:]
        if len(d) in (10, 11) and '11' <= d[:2] <= '99':
            return d
    return ''


def decidir_entrada(conn, identificador, agora_sp, *outros):
    """Ligacao chegando pelo tronco. `identificador` e os `outros` sao tentados em ordem
    (ver numero_do_identificador). Retorna (resultado, dados):
         ('ALLOW', {'numero', 'nome', 'ids': [...], 'dial'}) ou
         ('BLOCK_UNKNOWN'|'BLOCK_SCHEDULE_DEST'|'BLOCK_NO_PHONE', {'numero': ...})."""
    d = numero_do_identificador(identificador, *outros)
    if not d:
        return 'BLOCK_UNKNOWN', {'numero': re.sub(r'\D', '', identificador or '')}
    tel = familia_por_numero(conn, d)
    if not tel:
        return 'BLOCK_UNKNOWN', {'numero': d}
    ids, fora_horario = [], False
    for c in svc_cri.listar(conn, tel['familia_id']):
        aparelho = svc_tel.atual_da_crianca(conn, c['id'])
        if not aparelho or aparelho['estado'] not in ESTADOS_TOCAM:
            continue
        if not horarios.dentro_do_horario(conn, c['id_rede'], agora_sp):
            fora_horario = True
            continue
        ids.append(c['id_rede'])
    nome = tel['apelido'] or 'Família'
    if not ids:
        return ('BLOCK_SCHEDULE_DEST' if fora_horario else 'BLOCK_NO_PHONE'), {'numero': d, 'nome': nome}
    from . import custos
    from .contas import _cfg
    limites = {i: custos.segundos_permitidos(conn, _cfg(), i, 'entrada', agora_sp) for i in ids}
    ids = [i for i in ids if limites[i] > 0]
    if not ids:
        return 'BLOCK_TETO', {'numero': d, 'nome': nome}
    return 'ALLOW', {'numero': d, 'nome': nome, 'ids': ids, 'dial': '&'.join(f'PJSIP/{i}' for i in ids),
                     'limite_s': min(limites[i] for i in ids)}
