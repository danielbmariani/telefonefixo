#!/usr/bin/env python3
"""
ids.py — Numeracao e apelidos da rede aberta.

Plano de numeracao (doc 03):
    1XX            servicos (100 = hora certa)
    [2-7]XXXXX     ID de crianca (6 digitos, aleatorio)
    0[1-9]         grupo para ligar juntos (codigo do cartao da propria crianca, doc 16)
    9[2-7]XXXXX    celular 1 da familia da crianca
    8[2-7]XXXXX    celular 2 da familia da crianca
"""

import re
import secrets

ID_RE = re.compile(r'^[2-7]\d{5}$')
NICK_RE = re.compile(r'^[a-z][a-z0-9_]{2,19}$')
PRIMEIRO_DIGITO = '234567'
ESPACO_IDS = 6 * 100_000  # 600.000

# Palavras que nao podem ser apelido (ampliar com a ONG)
NICKS_PROIBIDOS = {'admin', 'suporte', 'ong', 'teste', 'root', 'sistema'}


def gerar_id(existe):
    """Sorteia um ID de 6 digitos que nao exista. `existe` e uma funcao
    id -> bool (consulta ao banco). Levanta RuntimeError se o espaco
    estiver quase cheio (mais de 1000 tentativas)."""
    for _ in range(1000):
        candidato = secrets.choice(PRIMEIRO_DIGITO) + f'{secrets.randbelow(100_000):05d}'
        if not existe(candidato):
            return candidato
    raise RuntimeError('espaco de IDs esgotado')


def formatar_id(id_):
    """'345678' -> '34 56 78' (para cartao e tela)."""
    if not ID_RE.match(id_):
        raise ValueError(f'ID invalido: {id_!r}')
    return f'{id_[0:2]} {id_[2:4]} {id_[4:6]}'


def validar_nick(nick):
    """Apelido: 3 a 20 caracteres, comeca com letra, so minusculas, digitos e _.
    Retorna o apelido normalizado ou levanta ValueError com mensagem para o
    usuario."""
    n = (nick or '').strip().lower()
    if not NICK_RE.match(n):
        raise ValueError('Apelido deve ter de 3 a 20 caracteres, comecar com letra '
                         'e usar so letras minusculas, numeros e _')
    if n in NICKS_PROIBIDOS:
        raise ValueError('Esse apelido nao pode ser usado')
    if re.search(r'\d{4,}', n):
        raise ValueError('Evite sequencias longas de numeros (parecem data ou telefone)')
    return n


def classificar_discado(digitos):
    """Interpreta o que a crianca discou. Retorna (tipo, id) ou (tipo, None):
        ('servico', '100'), ('crianca', '345678'), ('grupo', '1'),
        ('familia1', '345678'), ('familia2', '345678'), ('invalido', None)."""
    d = (digitos or '').strip()
    if re.match(r'^1\d{2}$', d):
        return ('servico', d)
    if ID_RE.match(d):
        return ('crianca', d)
    if re.match(r'^0[1-9]$', d):
        return ('grupo', d[1])
    if len(d) == 7 and ID_RE.match(d[1:]) and d[0] in '98':
        return ('familia1' if d[0] == '9' else 'familia2', d[1:])
    return ('invalido', None)


def ramal_familia(id_, slot):
    """ID da crianca -> ramal SIP do celular da familia (slot 1 ou 2)."""
    if not ID_RE.match(id_):
        raise ValueError(f'ID invalido: {id_!r}')
    if slot not in (1, 2):
        raise ValueError('slot deve ser 1 ou 2')
    return ('9' if slot == 1 else '8') + id_
