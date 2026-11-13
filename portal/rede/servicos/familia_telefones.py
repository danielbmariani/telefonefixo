"""
familia_telefones.py — Telefones da familia (doc 08 item 6c e item 25; bancada B23, B30, B31; docs 19 e 20).

Dois tipos na mesma tabela:
- Celulares de casa (posicao 1 e 2): a crianca disca 9 + o proprio ID para o celular 1 e 8 + ID para o
  celular 2 (decisao do Daniel em 27/10: um jeito de discar para cada, no maximo dois).
- Outros telefones (posicao NULL, ate MAX_OUTROS): a vo, a casa de um amigo, a padaria. A crianca disca o
  numero: so o numero quando e do DDD da casa, DDD + numero quando e de fora (doc 20). A central casa o
  discado com a lista pelo fim do numero (casar_discado), sem depender do DDD da casa.

Entrada: quando um numero cadastrado com `recebe` liga para o numero da rede, a central reconhece e faz
tocar o telefone das criancas daquela familia. Numero desconhecido, ou cadastrado sem `recebe`, nao toca.

Numeros guardados so com digitos, no formato nacional: DDD + numero (10 ou 11 digitos).
"""

import re

from sqlalchemy import select, insert, update, and_

from .. import db, auditoria, ddd as svc_ddd
from ..tempo import agora
from . import criancas as svc_cri, telefones as svc_tel, horarios
from .contas import ErroUsuario

MAX_POR_FAMILIA = 2                # celulares de casa (com atalho)
MAX_OUTROS_PADRAO = 20
PREFIXOS = {1: '9', 2: '8'}        # posicao -> digito que a crianca disca antes do proprio ID
TRONCO_ENDPOINT = 'nvoip'          # nome do endpoint PJSIP do tronco (deploy/tronco.sh)
ESTADOS_TOCAM = ('registrado', 'ativo')
APELIDO_MAX = 20

# Numeros de servico (nao geograficos): nao sao telefone de alguem e nao entram na lista (doc 20, 2.1).
# Como sao discados: 0800 123 4567, 0300 313 1234, 4004 1234 (tarifa local, sem DDD).
_SERVICO_0X00 = ('0300', '0303', '0500', '0800', '0900')
_ERRO_SERVICO = 'Esse é um número de serviço (0800, 0300, 4004), não de uma pessoa. Não dá para cadastrar.'


def normalizar(numero, ddd_casa=None):
    """'+55 (11) 98765-4321' -> '11987654321'. Com ddd_casa, aceita tambem so o numero ('3456 7890' -> '1134567890').
    Levanta ErroUsuario se nao for um telefone brasileiro fixo ou celular."""
    bruto = (numero or '').strip()
    d = re.sub(r'\D', '', bruto)
    if d[:4] in _SERVICO_0X00 or (len(d) == 10 and d[:3] in ('300', '303', '500', '800', '900')):
        raise ErroUsuario(_ERRO_SERVICO)
    if d.startswith('55') and len(d) in (12, 13):
        d = d[2:]
    elif bruto.startswith('+') or d.startswith('00'):
        # Codigo de outro pais: o tronco so disca numero nacional (doc 17: pai no exterior e caso do WhatsApp)
        raise ErroUsuario('Só telefone brasileiro, com DDD. Número de outro país não pode ser cadastrado.')
    if d.startswith('0') and len(d) in (11, 12):
        d = d[1:]
    if len(d) in (8, 9) and ddd_casa:
        d = ddd_casa + d
    if len(d) not in (10, 11):
        if ddd_casa:
            raise ErroUsuario('Digite o número, com ou sem DDD, por exemplo 3456 7890 ou 11 3456 7890.')
        raise ErroUsuario('Digite o número com DDD, por exemplo 11 98765 4321.')
    ddd, local = d[:2], d[2:]
    if ddd not in svc_ddd.DDDS:
        raise ErroUsuario('DDD inválido.')
    if len(local) == 9 and local[0] != '9':
        raise ErroUsuario('Celular com 9 dígitos começa com 9 depois do DDD.')
    if len(local) == 8 and local[0] not in '2345':
        raise ErroUsuario('Telefone fixo começa com 2, 3, 4 ou 5 depois do DDD.')
    if local.startswith('400'):
        raise ErroUsuario(_ERRO_SERVICO)
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
    """Todos os telefones da familia: celulares de casa (posicao 1 e 2) primeiro, depois os outros por ordem de
    cadastro."""
    cond = db.familia_telefones.c.familia_id == familia_id
    if so_ativos:
        cond = and_(cond, db.familia_telefones.c.ativo.is_(True))
    rows = conn.execute(select(db.familia_telefones).where(cond)).mappings().all()
    return sorted(rows, key=lambda t: (t['posicao'] is None, t['posicao'] or 0, t['id']))


def listar_atalhos(conn, familia_id):
    return [t for t in listar(conn, familia_id) if t['posicao'] in PREFIXOS]


def listar_outros(conn, familia_id):
    return [t for t in listar(conn, familia_id) if t['posicao'] is None]


def por_posicao(conn, familia_id, posicao):
    return next((t for t in listar_atalhos(conn, familia_id) if t['posicao'] == posicao), None)


def por_id(conn, familia_id, telefone_id):
    return conn.execute(select(db.familia_telefones).where(and_(db.familia_telefones.c.id == telefone_id,
                                                                db.familia_telefones.c.familia_id == familia_id))).mappings().first()


def trocar_ordem(conn, familia_id):
    """Celular 1 vira 2 e vice-versa."""
    ativos = listar_atalhos(conn, familia_id)
    if len(ativos) < 2:
        raise ErroUsuario('Só dá para trocar a ordem com dois celulares cadastrados.')
    for t, nova in zip(ativos[:2], (2, 1)):
        conn.execute(update(db.familia_telefones).where(db.familia_telefones.c.id == t['id']).values(posicao=nova))
    auditoria.registrar(conn, 'familia_telefones_ordem_trocada', 'familia', familia_id, 'familia', familia_id)


def adicionar(conn, familia_id, numero, apelido, atalho=True, recebe=True, ddd_casa=None, max_outros=MAX_OUTROS_PADRAO):
    """Cadastra um telefone. atalho=True: celular de casa, ganha a primeira posicao livre (9 ou 8 + ID).
    atalho=False: outro telefone, sem posicao, discado pelo numero. Retorna o numero normalizado."""
    n = normalizar(numero, ddd_casa)
    ativos = listar(conn, familia_id)
    repetido = next((t for t in ativos if t['numero'] == n), None)
    if repetido:
        raise ErroUsuario(f'Esse número já está cadastrado{" como " + repetido["apelido"] if repetido["apelido"] else ""}.')
    if atalho:
        atalhos = [t for t in ativos if t['posicao'] in PREFIXOS]
        if len(atalhos) >= MAX_POR_FAMILIA:
            raise ErroUsuario(f'No máximo {MAX_POR_FAMILIA} números por família. Remova um para adicionar outro.')
        posicao = min(set(PREFIXOS) - {t['posicao'] for t in atalhos})   # primeira posicao livre
    else:
        if max_outros <= 0:
            raise ErroUsuario('O cadastro de outros telefones está desligado.')
        if len([t for t in ativos if t['posicao'] is None]) >= max_outros:
            raise ErroUsuario(f'A lista está cheia ({max_outros} telefones). Remova um para adicionar outro.')
        posicao = None
    antigo = conn.execute(select(db.familia_telefones).where(and_(db.familia_telefones.c.familia_id == familia_id,
                                                                  db.familia_telefones.c.numero == n))).mappings().first()
    valores = {'apelido': limpar_apelido(apelido), 'ativo': True, 'criado_em': agora(), 'posicao': posicao, 'recebe': bool(recebe)}
    if antigo:
        conn.execute(update(db.familia_telefones).where(db.familia_telefones.c.id == antigo['id']).values(**valores))
        novo_id = antigo['id']
    else:
        novo_id = conn.execute(insert(db.familia_telefones).values(familia_id=familia_id, numero=n, **valores)).inserted_primary_key[0]
    auditoria.registrar(conn, 'familia_telefone_adicionado', 'familia', familia_id, 'familia_telefone', novo_id,
                        {'numero': n[:2] + '*****' + n[-4:], 'tipo': 'celular' if atalho else 'outro', 'recebe': bool(recebe)})
    return n


def remover(conn, familia_id, telefone_id):
    r = conn.execute(update(db.familia_telefones).where(and_(db.familia_telefones.c.id == telefone_id,
                                                              db.familia_telefones.c.familia_id == familia_id))
                     .values(ativo=False, posicao=None))
    if r.rowcount:
        auditoria.registrar(conn, 'familia_telefone_removido', 'familia', familia_id, 'familia_telefone', telefone_id)
    return bool(r.rowcount)


def mudar_recebe(conn, familia_id, telefone_id, recebe):
    """Liga ou desliga "esse telefone tambem pode ligar para a crianca"."""
    r = conn.execute(update(db.familia_telefones).where(and_(db.familia_telefones.c.id == telefone_id,
                                                              db.familia_telefones.c.familia_id == familia_id,
                                                              db.familia_telefones.c.ativo.is_(True)))
                     .values(recebe=bool(recebe)))
    if r.rowcount:
        auditoria.registrar(conn, 'familia_telefone_recebe', 'familia', familia_id, 'familia_telefone', telefone_id,
                            {'recebe': bool(recebe)})
    return bool(r.rowcount)


def apelido_do_numero(conn, familia_id, numero):
    """Nome que a familia deu ao numero (ativo primeiro; se removido, o ultimo nome), ou None."""
    rows = conn.execute(select(db.familia_telefones.c.apelido, db.familia_telefones.c.ativo)
                        .where(and_(db.familia_telefones.c.familia_id == familia_id, db.familia_telefones.c.numero == numero))
                        .order_by(db.familia_telefones.c.ativo.desc(), db.familia_telefones.c.id.desc())).first()
    return (rows[0] or None) if rows else None


def casar_discado(conn, familia_id, tipo, digitos, ddd_casa=None):
    """O que a crianca discou -> numero da lista da familia. tipo 'externo' (DDD + numero) casa o numero inteiro;
    'externo_local' (so o numero) casa pelo fim: uma entrada, e ela; mais de uma, vale a do DDD da casa.
    Retorna (numero, None) ou (None, 'EXTERNO_FORA_DA_LISTA' | 'EXTERNO_AMBIGUO')."""
    ativos = listar(conn, familia_id)
    if tipo == 'externo':
        achado = next((t for t in ativos if t['numero'] == digitos), None)
        return (achado['numero'], None) if achado else (None, 'EXTERNO_FORA_DA_LISTA')
    iguais = [t for t in ativos if svc_ddd.parte_local(t['numero']) == digitos]
    if not iguais:
        return None, 'EXTERNO_FORA_DA_LISTA'
    if len(iguais) == 1:
        return iguais[0]['numero'], None
    da_casa = [t for t in iguais if ddd_casa and t['numero'][:2] == ddd_casa]
    if len(da_casa) == 1:
        return da_casa[0]['numero'], None
    return None, 'EXTERNO_AMBIGUO'


def _candidatos(numero):
    """O numero e a versao com/sem o nono digito: operadoras entregam o identificador dos dois jeitos."""
    c = {numero}
    if len(numero) == 11 and numero[2] == '9':
        c.add(numero[:2] + numero[3:])
    elif len(numero) == 10:
        c.add(numero[:2] + '9' + numero[2:])
    return list(c)


def familias_por_numero(conn, numero):
    """Numero (ja normalizado) -> linhas ativas e com `recebe` de familia_telefones, uma por familia, na ordem de
    cadastro. Mais de uma linha = o mesmo telefone cadastrado por mais de uma familia (doc 20, 3.3)."""
    rows = conn.execute(select(db.familia_telefones).where(and_(db.familia_telefones.c.numero.in_(_candidatos(numero)),
                                                                db.familia_telefones.c.ativo.is_(True),
                                                                db.familia_telefones.c.recebe.is_(True)))
                        .order_by(db.familia_telefones.c.id)).mappings().all()
    por_familia = {}
    for r in sorted(rows, key=lambda r: (r['numero'] != numero, r['id'])):   # exato antes do sem nono digito
        por_familia.setdefault(r['familia_id'], r)
    return sorted(por_familia.values(), key=lambda r: r['id'])


def familia_por_numero(conn, numero):
    """A primeira familia que cadastrou o numero, ou None (ver familias_por_numero)."""
    fams = familias_por_numero(conn, numero)
    return fams[0] if fams else None


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


MENU_MAX = 9   # opcoes do menu de entrada: uma tecla por crianca


def _criancas_que_tocam(conn, familia_id, agora_sp, cfg):
    """[(crianca, limite_s)] da familia com telefone conectado, dentro do horario e com minutos; e se alguma ficou
    de fora por horario."""
    from . import custos
    tocam, fora_horario = [], False
    for c in svc_cri.listar(conn, familia_id):
        aparelho = svc_tel.atual_da_crianca(conn, c['id'])
        if not aparelho or aparelho['estado'] not in ESTADOS_TOCAM:
            continue
        if not horarios.dentro_do_horario(conn, c['id_rede'], agora_sp):
            fora_horario = True
            continue
        tocam.append((c, custos.segundos_permitidos(conn, cfg, c['id_rede'], 'entrada', agora_sp)))
    return tocam, fora_horario


def decidir_entrada(conn, identificador, agora_sp, *outros):
    """Ligacao chegando pelo tronco. `identificador` e os `outros` sao tentados em ordem
    (ver numero_do_identificador). Retorna (resultado, dados):
         ('ALLOW', {'numero', 'nome', 'ids': [...], 'dial', 'limite_s'}) quando o numero e de uma familia so;
         ('MENU', {'numero', 'nome', 'opcoes': [{'id_rede', 'apelido', 'nome', 'limite_s'}, ...]}) quando o mesmo
             numero esta em mais de uma familia: a central pergunta com quem a pessoa quer falar (doc 20, 3.3);
         ('BLOCK_UNKNOWN'|'BLOCK_SCHEDULE_DEST'|'BLOCK_NO_PHONE'|'BLOCK_TETO', {'numero': ...})."""
    from .contas import _cfg
    d = numero_do_identificador(identificador, *outros)
    if not d:
        return 'BLOCK_UNKNOWN', {'numero': re.sub(r'\D', '', identificador or '')}
    fams = familias_por_numero(conn, d)
    if not fams:
        return 'BLOCK_UNKNOWN', {'numero': d}
    cfg = _cfg()
    nome = fams[0]['apelido'] or 'Família'
    por_familia, fora_horario, sem_minutos = [], False, False
    for tel in fams:
        tocam, fora = _criancas_que_tocam(conn, tel['familia_id'], agora_sp, cfg)
        fora_horario = fora_horario or fora
        com_minutos = [(c, lim) for c, lim in tocam if lim > 0]
        sem_minutos = sem_minutos or (bool(tocam) and not com_minutos)
        if com_minutos:
            por_familia.append((tel, com_minutos))
    if not por_familia:
        if sem_minutos:
            return 'BLOCK_TETO', {'numero': d, 'nome': nome}
        return ('BLOCK_SCHEDULE_DEST' if fora_horario else 'BLOCK_NO_PHONE'), {'numero': d, 'nome': nome}
    if len(por_familia) == 1:
        tel, tocam = por_familia[0]
        ids = [c['id_rede'] for c, _ in tocam]
        return 'ALLOW', {'numero': d, 'nome': tel['apelido'] or 'Família', 'ids': ids,
                         'dial': '&'.join(f'PJSIP/{i}' for i in ids), 'limite_s': min(lim for _, lim in tocam)}
    opcoes = [{'id_rede': c['id_rede'], 'apelido': c['apelido'], 'nome_crianca': c['nome'], 'nome': tel['apelido'] or 'Família',
               'limite_s': lim} for tel, tocam in por_familia for c, lim in tocam][:MENU_MAX]
    _escolher_sons(opcoes, cfg)
    return 'MENU', {'numero': d, 'nome': nome, 'opcoes': opcoes}


def _chave_nome(n):
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFKD', (n or '').lower()) if not unicodedata.combining(ch)).strip()


def _escolher_sons(opcoes, cfg):
    """Que audio o menu toca para cada opcao: o nome falado da crianca (criancas.nome) quando ela tem um e nenhuma
    outra opcao tem o mesmo nome; senao o apelido, que e unico na rede."""
    from .. import voz
    repetidos = {}
    for o in opcoes:
        k = _chave_nome(o.get('nome_crianca'))
        if k:
            repetidos[k] = repetidos.get(k, 0) + 1
    for o in opcoes:
        k = _chave_nome(o.get('nome_crianca'))
        if k and repetidos.get(k, 0) == 1 and voz.tem_nome(cfg, o['id_rede']):
            o['som'] = f"nomes/{o['id_rede']}"
        else:
            o['som'] = f"apelidos/{o['id_rede']}"
