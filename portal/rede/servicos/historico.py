"""historico.py — Historico de chamadas (call_logs), igual ao projeto atual, por ID de 6 digitos."""

from sqlalchemy import select, or_, func, and_, text

from .. import db


def listar(conn, id_rede, pagina=1, por_pagina=100):
    cond = or_(db.call_logs.c.caller_ext == id_rede, db.call_logs.c.callee_ext == id_rede)
    total = conn.execute(select(func.count()).select_from(db.call_logs).where(cond)).scalar()
    rows = conn.execute(select(db.call_logs).where(cond).order_by(db.call_logs.c.timestamp.desc())
                        .limit(por_pagina).offset((pagina - 1) * por_pagina)).mappings().all()
    return rows, total


def tempo_total(conn, id_rede):
    return conn.execute(select(func.coalesce(func.sum(db.call_logs.c.duration_seconds), 0)).where(and_(
        or_(db.call_logs.c.caller_ext == id_rede, db.call_logs.c.callee_ext == id_rede),
        db.call_logs.c.status == 'ALLOWED', db.call_logs.c.duration_seconds > 0))).scalar()


def nomes(conn, ids_rede):
    """id_rede -> apelido. Tambem rotula o celular da familia: '9'+ID (saida pelo tronco) e o numero
    do celular (entrada pelo tronco) viram 'Celular da família' com o numero formatado."""
    if not ids_rede:
        return {}
    ids = list(ids_rede)
    rows = conn.execute(select(db.criancas.c.id_rede, db.criancas.c.apelido).where(db.criancas.c.id_rede.in_(ids))).all()
    res = {i: a for i, a in rows}
    # chamada em grupo: 'GRUPO:<id>' vira o nome do grupo (mesmo se o grupo ja acabou); 'GRUPO' sem id e de antes de 28/10
    gids = {}
    for i in ids:
        if i and i.startswith('GRUPO:') and i[6:].isdigit():
            gids[int(i[6:])] = i
        elif i == 'GRUPO':
            res[i] = 'Chamada em grupo'
    if gids:
        for gid, nome in conn.execute(select(db.grupos.c.id, db.grupos.c.nome).where(db.grupos.c.id.in_(list(gids)))).all():
            res[gids[gid]] = f'{nome} (grupo)'
        for gid, chave in gids.items():
            res.setdefault(chave, 'Chamada em grupo')
    for i in ids:
        if i in res or not i:
            continue
        if len(i) == 7 and i[0] in '98' and i[1:].isdigit():
            res[i] = 'Celular 1 da família' if i[0] == '9' else 'Celular 2 da família'
        elif i.isdigit() and len(i) in (10, 11):
            from .familia_telefones import formatar
            res[i] = f'Celular da família {formatar(i)}'
    return res


def tempo_por_contato(conn, id_rede):
    res = []
    rows = conn.execute(text(
        "SELECT CASE WHEN caller_ext = :e THEN callee_ext ELSE caller_ext END AS contato, "
        "substr(timestamp, 1, 10) AS dt, SUM(duration_seconds) AS secs FROM call_logs "
        "WHERE (caller_ext = :e OR callee_ext = :e) AND callee_ext NOT LIKE 'GRUPO%' AND status = 'ALLOWED' "
        "AND duration_seconds > 0 GROUP BY contato, dt"), {'e': id_rede}).all()
    for contato, dt, secs in rows:
        res.append({'contact_ext': contato, 'date': dt, 'seconds': int(secs or 0)})
    grupo = conn.execute(select(db.call_logs.c.timestamp, db.call_logs.c.block_reason).where(and_(
        db.call_logs.c.caller_ext == id_rede, db.call_logs.c.callee_ext.like('GRUPO%'),
        db.call_logs.c.status == 'ALLOWED', db.call_logs.c.block_reason.isnot(None)))).all()
    for ts, det in grupo:
        try:
            for part in (det or '').split(','):
                ext, s = part.split(':')
                res.append({'contact_ext': ext.strip(), 'date': ts[:10], 'seconds': int(s)})
        except (ValueError, IndexError):
            pass
    return res


def primeira_chamada_registrada(conn, id_rede, desde=None):
    """Para o observador: ha alguma chamada ALLOWED feita por este ID (inclusive 100), ou recebida e
    atendida por ele, a partir de `desde` (o registro SIP deste aparelho)? Sem `desde`, qualquer uma.
    Atender tambem prova que o telefone funciona (bancada 26/10/2026: o aparelho 2 so recebeu a
    primeira ligacao). Com `desde`, um telefone reativado nao vira "ativo" por ligacoes antigas (B12)."""
    fez = and_(db.call_logs.c.caller_ext == id_rede, db.call_logs.c.status == 'ALLOWED')
    atendeu = and_(db.call_logs.c.callee_ext == id_rede, db.call_logs.c.status == 'ALLOWED',
                   db.call_logs.c.duration_seconds > 0)
    cond = or_(fez, atendeu)
    if desde:
        from ..tempo import texto_sp
        cond = and_(cond, db.call_logs.c.timestamp >= texto_sp(desde, '%Y-%m-%d %H:%M:%S'))
    return conn.execute(select(db.call_logs.c.id).where(cond).limit(1)).first() is not None


PERDIDAS = ('NOANSWER', 'BUSY', 'CANCEL')


def para_retornar(conn, id_rede, dias=7):
    """Quem ligou para esta crianca e nao foi atendido, sem conversa depois disso (em qualquer
    direcao). Para a tela do historico: "quem precisa de retorno". Item 5 do doc 12."""
    from datetime import datetime, timedelta
    from ..tempo import TZ_SP
    desde = (datetime.now(TZ_SP) - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
    rows = conn.execute(select(db.call_logs).where(and_(
        or_(db.call_logs.c.caller_ext == id_rede, db.call_logs.c.callee_ext == id_rede),
        db.call_logs.c.timestamp >= desde, db.call_logs.c.callee_ext.not_like('GRUPO%')))
        .order_by(db.call_logs.c.timestamp)).mappings().all()
    pend = {}
    for r in rows:
        outro = r['caller_ext'] if r['callee_ext'] == id_rede else r['callee_ext']
        if r['status'] == 'ALLOWED':
            pend.pop(outro, None)                       # conversaram depois: nada a retornar
        elif r['callee_ext'] == id_rede and r['status'] in PERDIDAS:
            p = pend.setdefault(outro, {'contato': outro, 'vezes': 0, 'ultima': r['timestamp']})
            p['vezes'] += 1
            p['ultima'] = r['timestamp']
    return sorted(pend.values(), key=lambda x: x['ultima'], reverse=True)
