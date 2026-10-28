"""grupos.py — Grupos para ligar juntos (doc 16).

Os pais montam o grupo no site a partir dos amigos aceitos da crianca dona. Cada membro (a dona
inclusive) recebe um codigo de 1 digito, proprio do cartao dele: disca 0 + codigo e a central toca para
todos. Regra fixa: so entra na chamada quem e amigo aceito de todos os que ja estao nela (clique);
quem nao e, fica de fora com o motivo, sem que o site conte a uma familia quem e amigo de quem entre
as outras criancas.
"""

from sqlalchemy import select, insert, update, and_

from .. import db, auditoria, voz
from ..tempo import agora
from .contas import ErroUsuario, _cfg
from . import criancas as svc_cri, amizades as svc_ami, horarios as svc_hor

NOME_MIN, NOME_MAX = 2, 20
MAX_MEMBROS = 4                 # contando a dona: igual ao limite da chamada, para todo o grupo caber nela (decisao de 28/10)
MAX_GRUPOS_POR_CRIANCA = 9      # codigos 1..9
CODIGOS = range(1, 10)


def limpar_nome(nome):
    n = ' '.join((nome or '').split())
    if len(n) < NOME_MIN or len(n) > NOME_MAX:
        raise ErroUsuario(f'O nome do grupo deve ter de {NOME_MIN} a {NOME_MAX} caracteres (ele aparece no visor do telefone).')
    return n


def por_id(conn, grupo_id):
    return conn.execute(select(db.grupos).where(db.grupos.c.id == grupo_id)).mappings().first()


def _membros_ativos(conn, grupo_id):
    return conn.execute(select(db.grupo_membros).where(and_(db.grupo_membros.c.grupo_id == grupo_id,
                                                              db.grupo_membros.c.saiu_em.is_(None)))
                        .order_by(db.grupo_membros.c.entrou_em, db.grupo_membros.c.id)).mappings().all()


def _codigos_usados(conn, crianca_id):
    rows = conn.execute(select(db.grupo_membros.c.codigo).join(db.grupos, db.grupos.c.id == db.grupo_membros.c.grupo_id)
                        .where(and_(db.grupo_membros.c.crianca_id == crianca_id, db.grupo_membros.c.saiu_em.is_(None),
                                    db.grupos.c.ativo.is_(True)))).scalars().all()
    return set(rows)


def _codigo_livre(conn, crianca_id):
    usados = _codigos_usados(conn, crianca_id)
    for c in CODIGOS:
        if c not in usados:
            return c
    return None


def _amigos_ids(conn, crianca_id):
    """ids (da tabela criancas) dos amigos aceitos."""
    rows = conn.execute(select(db.amizades).where(and_(
        db.amizades.c.estado == 'aceita',
        (db.amizades.c.de_crianca_id == crianca_id) | (db.amizades.c.para_crianca_id == crianca_id)))).mappings().all()
    return {r['para_crianca_id'] if r['de_crianca_id'] == crianca_id else r['de_crianca_id'] for r in rows}


def criar(conn, familia_id, dona, nome, membros_ids):
    """`dona` e a linha da crianca da familia; `membros_ids` sao ids de criancas (amigos aceitos da dona)."""
    nome = limpar_nome(nome)
    ids_ = []
    for m in membros_ids or []:
        try:
            m = int(m)
        except (TypeError, ValueError):
            continue
        if m != dona['id'] and m not in ids_:
            ids_.append(m)
    if not ids_:
        raise ErroUsuario('Escolha pelo menos um amigo para o grupo.')
    if len(ids_) + 1 > MAX_MEMBROS:
        raise ErroUsuario(f'Um grupo tem no máximo {MAX_MEMBROS} crianças, contando {dona["apelido"]}.')
    amigos = _amigos_ids(conn, dona['id'])
    if any(m not in amigos for m in ids_):
        raise ErroUsuario('Só entram no grupo amigos já aceitos.')
    if _codigo_livre(conn, dona['id']) is None:
        raise ErroUsuario(f'{dona["apelido"]} já está em {MAX_GRUPOS_POR_CRIANCA} grupos. Saia de um para criar outro.')
    sem_codigo = [svc_cri.por_id(conn, m)['apelido'] for m in ids_ if _codigo_livre(conn, m) is None]
    if sem_codigo:
        raise ErroUsuario(f'{", ".join(sem_codigo)} já está em {MAX_GRUPOS_POR_CRIANCA} grupos e não pode entrar em mais um.')
    r = conn.execute(insert(db.grupos).values(nome=nome, crianca_dona_id=dona['id'], ativo=True, criado_em=agora()))
    gid = r.inserted_primary_key[0]
    for cid in [dona['id']] + ids_:
        conn.execute(insert(db.grupo_membros).values(grupo_id=gid, crianca_id=cid, codigo=_codigo_livre(conn, cid),
                                                      entrou_em=agora()))
    auditoria.registrar(conn, 'grupo_criado', 'familia', familia_id, 'grupo', gid,
                        detalhes={'nome': nome, 'membros': len(ids_) + 1})
    try:
        voz.gerar_grupo(_cfg(), gid, nome)
    except Exception as e:  # voz nunca derruba a criacao
        auditoria.registrar(conn, 'voz_falhou', 'sistema', None, 'grupo', gid, detalhes={'erro': str(e)[:200]})
    return por_id(conn, gid)


def listar_da_crianca(conn, crianca):
    """Grupos ativos em que a crianca esta, com o codigo dela, os membros e o que falta (so dados dela:
    quem entre os membros ainda nao e amigo DELA). Nao revela amizades entre terceiros."""
    rows = conn.execute(select(db.grupo_membros, db.grupos.c.nome, db.grupos.c.crianca_dona_id)
                        .join(db.grupos, db.grupos.c.id == db.grupo_membros.c.grupo_id)
                        .where(and_(db.grupo_membros.c.crianca_id == crianca['id'], db.grupo_membros.c.saiu_em.is_(None),
                                    db.grupos.c.ativo.is_(True))).order_by(db.grupo_membros.c.codigo)).mappings().all()
    amigos = _amigos_ids(conn, crianca['id'])
    out = []
    for r in rows:
        membros = []
        faltam = []
        for m in _membros_ativos(conn, r['grupo_id']):
            c = svc_cri.por_id(conn, m['crianca_id'])
            if not c:
                continue
            eu = c['id'] == crianca['id']
            amigo = eu or c['id'] in amigos
            membros.append({'crianca_id': c['id'], 'apelido': c['apelido'], 'id_rede': c['id_rede'], 'eu': eu, 'amigo': amigo,
                            'dona': c['id'] == r['crianca_dona_id']})
            if not amigo:
                faltam.append(c['apelido'])
        dona = svc_cri.por_id(conn, r['crianca_dona_id'])
        out.append({'id': r['grupo_id'], 'nome': r['nome'], 'codigo': r['codigo'], 'discar': f'0{r["codigo"]}',
                    'dona': r['crianca_dona_id'] == crianca['id'], 'dona_apelido': dona['apelido'] if dona else '?',
                    'membros': membros, 'faltam': faltam})
    return out


def para_cartao(conn, crianca):
    return [(g['nome'], g['discar']) for g in listar_da_crianca(conn, crianca)]


def _membro(conn, grupo_id, crianca_id):
    return conn.execute(select(db.grupo_membros).where(and_(db.grupo_membros.c.grupo_id == grupo_id,
                                                              db.grupo_membros.c.crianca_id == crianca_id,
                                                              db.grupo_membros.c.saiu_em.is_(None)))).mappings().first()


def sair(conn, familia_id, grupo_id, crianca):
    """A familia tira a propria crianca. Com menos de 2 membros o grupo e encerrado."""
    g = por_id(conn, grupo_id)
    m = _membro(conn, grupo_id, crianca['id']) if g else None
    if not g or not g['ativo'] or not m:
        raise ErroUsuario('Grupo não encontrado.')
    conn.execute(update(db.grupo_membros).where(db.grupo_membros.c.id == m['id']).values(saiu_em=agora()))
    auditoria.registrar(conn, 'grupo_saiu', 'familia', familia_id, 'grupo', grupo_id, detalhes={'crianca_id': crianca['id']})
    if len(_membros_ativos(conn, grupo_id)) < 2:
        _encerrar(conn, grupo_id, 'ficou_sem_membros')


def remover(conn, familia_id, grupo_id, crianca):
    """So a familia da dona apaga o grupo inteiro."""
    g = por_id(conn, grupo_id)
    if not g or not g['ativo'] or g['crianca_dona_id'] != crianca['id']:
        raise ErroUsuario('Só quem criou o grupo pode removê-lo.')
    _encerrar(conn, grupo_id, 'removido_pela_dona')
    auditoria.registrar(conn, 'grupo_removido', 'familia', familia_id, 'grupo', grupo_id)


def _encerrar(conn, grupo_id, motivo):
    conn.execute(update(db.grupos).where(db.grupos.c.id == grupo_id).values(ativo=False))
    conn.execute(update(db.grupo_membros).where(and_(db.grupo_membros.c.grupo_id == grupo_id,
                                                      db.grupo_membros.c.saiu_em.is_(None))).values(saiu_em=agora()))
    auditoria.registrar(conn, 'grupo_encerrado', 'sistema', None, 'grupo', grupo_id, detalhes={'motivo': motivo})


def amigos_para_grupo(conn, crianca, preselecao=None):
    """Lista para o formulario: amigos aceitos da crianca, com os pre-selecionados (atalho da turma)."""
    pre = set(preselecao or [])
    lst = svc_ami.listar(conn, crianca['id'])
    out = []
    for a in lst['amigos']:
        c = svc_cri.por_id_rede(conn, a['id_rede'])
        if c:
            out.append({'crianca_id': c['id'], 'apelido': c['apelido'], 'marcado': c['id'] in pre})
    return out


# --- Decisao da chamada (usada pelo servico ARI) ---

def decidir(conn, caller_id_rede, codigo, agora_sp):
    """A crianca `caller` discou 0 + codigo. Devolve um dicionario:
       resultado: ALLOW | BLOCK_UNKNOWN | BLOCK_SCHEDULE_CALLER
       grupo: {id, nome}; caller: {id_rede, apelido}
       chamar: [{id_rede, apelido}] em ordem de entrada no grupo; fora: [{id_rede, apelido, motivo}]
       motivo: 'horario' (fora do horario ou silenciado), 'amizade' (nao e amigo de todos os que vao), 'inativa'
    A regra do clique e aplicada em ordem de entrada no grupo: um membro so entra na lista se for amigo
    aceito de quem liga e de todos os ja escolhidos."""
    quem = svc_cri.por_id_rede(conn, caller_id_rede)
    if not quem or not quem['ativa']:
        return {'resultado': 'BLOCK_UNKNOWN', 'motivo': 'CALLER_NOT_ACTIVATED'}
    try:
        codigo = int(codigo)
    except (TypeError, ValueError):
        return {'resultado': 'BLOCK_UNKNOWN', 'motivo': 'CODIGO_INVALIDO'}
    m = conn.execute(select(db.grupo_membros, db.grupos.c.nome)
                     .join(db.grupos, db.grupos.c.id == db.grupo_membros.c.grupo_id)
                     .where(and_(db.grupo_membros.c.crianca_id == quem['id'], db.grupo_membros.c.codigo == codigo,
                                 db.grupo_membros.c.saiu_em.is_(None), db.grupos.c.ativo.is_(True)))).mappings().first()
    if not m:
        return {'resultado': 'BLOCK_UNKNOWN', 'motivo': 'GRUPO_NAO_EXISTE'}
    if not svc_hor.dentro_do_horario(conn, caller_id_rede, agora_sp):
        return {'resultado': 'BLOCK_SCHEDULE_CALLER', 'motivo': 'SCHEDULE_CALLER',
                'grupo': {'id': m['grupo_id'], 'nome': m['nome']}}
    escolhidos = [caller_id_rede]
    chamar, fora = [], []
    for mem in _membros_ativos(conn, m['grupo_id']):
        if mem['crianca_id'] == quem['id']:
            continue
        c = svc_cri.por_id(conn, mem['crianca_id'])
        if not c or not c['ativa']:
            if c:
                fora.append({'id_rede': c['id_rede'], 'apelido': c['apelido'], 'motivo': 'inativa'})
            continue
        item = {'id_rede': c['id_rede'], 'apelido': c['apelido']}
        if not all(svc_ami.permitido(conn, c['id_rede'], e) for e in escolhidos):
            fora.append({**item, 'motivo': 'amizade'})
            continue
        if not svc_hor.dentro_do_horario(conn, c['id_rede'], agora_sp):
            fora.append({**item, 'motivo': 'horario'})
            continue
        escolhidos.append(c['id_rede'])
        chamar.append(item)
    return {'resultado': 'ALLOW', 'grupo': {'id': m['grupo_id'], 'nome': m['nome']},
            'caller': {'id_rede': quem['id_rede'], 'apelido': quem['apelido']}, 'chamar': chamar, 'fora': fora}


def pode_entrar(conn, id_rede, participantes_ids):
    """Entrada tardia ou atendimento: so se for amigo aceito de todos os que ja estao na chamada."""
    return all(svc_ami.permitido(conn, id_rede, p) for p in participantes_ids if p != id_rede)


def registrar_chamada(conn, tempos, quando_texto, atendida=True, grupo_id=None):
    """`tempos`: {id_rede: [(inicio_epoch, fim_epoch)]} por participante. Uma linha de call_logs por
    participante (callee 'GRUPO:<id do grupo>', para o historico mostrar o nome; duracao = tempo com alguem), com o tempo em comum com cada um dos outros em block_reason
    ('id:segundos,...'), como o historico ja mostra. `atendida=False` (ninguem entrou): status NOANSWER."""
    def total(iv, outros_ivs):
        # tempo em que este participante esteve na chamada com pelo menos um outro: toque, espera
        # sozinho e "voce e o unico" nao contam (pedido do Daniel, 28/10)
        pontos = sorted({p for a, b in iv for p in (a, b)} | {p for o in outros_ivs for a, b in o for p in (a, b)})
        s = 0
        for a, b in zip(pontos, pontos[1:]):
            eu = any(i <= a and b <= f for i, f in iv)
            alguem = any(i <= a and b <= f for o in outros_ivs for i, f in o)
            if eu and alguem:
                s += int(b - a)
        return s

    def comum(a, b):
        s = 0
        for i1, f1 in a:
            for i2, f2 in b:
                s += max(0, int(min(f1, f2) - max(i1, i2)))
        return s
    for pid, iv in tempos.items():
        outros = ','.join(f'{o}:{comum(iv, ov)}' for o, ov in tempos.items() if o != pid)
        dur = total(iv, [ov for o, ov in tempos.items() if o != pid])
        conn.execute(insert(db.call_logs).values(caller_ext=pid, callee_ext=f'GRUPO:{grupo_id}' if grupo_id else 'GRUPO', timestamp=quando_texto,
                                                 status='ALLOWED' if (dur > 0 and atendida) else 'NOANSWER', duration_seconds=dur,
                                                 block_reason=outros or None))
