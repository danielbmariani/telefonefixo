"""
reconciliacao.py — Jobs diarios (doc 09, secao 5) e export da auditoria com hash.
Divergencias viram casos; nada e corrigido automaticamente.
"""

import csv
import hashlib
import io
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, insert, and_, func

from .. import db, auditoria
from ..tempo import agora, utc
from . import criancas as svc_cri


def _caso(conn, tipo, descricao, detalhes, telefone_id=None, crianca_id=None, gravidade='media'):
    existe = conn.execute(select(db.casos.c.id).where(and_(db.casos.c.tipo == tipo, db.casos.c.estado == 'aberto',
                                                           db.casos.c.descricao == descricao))).first()
    if existe:
        return
    conn.execute(insert(db.casos).values(tipo=tipo, gravidade=gravidade, telefone_id=telefone_id, crianca_id=crianca_id,
                                         descricao=descricao, detalhes=detalhes, estado='aberto', criado_em=agora()))


def executar(conn, cfg, gdms_macs=None, ref=None):
    """gdms_macs: conjunto de MACs (12 hex) na organizacao do GDMS, se o chamador conseguiu listar."""
    ref = ref or agora()
    r = {'ramais_sem_linhas': 0, 'linhas_sem_crianca': 0, 'tokens_divergentes': 0,
         'estados_sem_fato': 0, 'gdms_orfaos': 0, 'gdms_faltando': 0, 'gdms_verificado': gdms_macs is not None}

    # 1. Asterisk x banco
    ativas = conn.execute(select(db.criancas).where(db.criancas.c.ativa == True)).mappings().all()  # noqa: E712
    ids_ativos = {c['id_rede'] for c in ativas}
    for c in ativas:
        if not svc_cri.ramal_consistente(conn, c):
            r['ramais_sem_linhas'] += 1
            _caso(conn, 'ramal_inconsistente', f'Criança {c["id_rede"]} ativa sem as 3 linhas ps_*', {'id_rede': c['id_rede']},
                  crianca_id=c['id'], gravidade='alta')
    for (idr,) in conn.execute(select(db.ps_endpoints.c.id)).all():
        if idr not in ids_ativos and idr.isdigit() and len(idr) == 6:
            r['linhas_sem_crianca'] += 1
            _caso(conn, 'ramal_orfao', f'ps_endpoints tem {idr} sem criança ativa', {'id_rede': idr}, gravidade='alta')

    # 2. Tokens: exatamente um ativo por telefone nao desativado; nenhum ativo em desativado
    for tel in conn.execute(select(db.telefones)).mappings().all():
        n = conn.execute(select(func.count()).select_from(db.prov_tokens).where(and_(
            db.prov_tokens.c.telefone_id == tel['id'], db.prov_tokens.c.ativo == True))).scalar()  # noqa: E712
        esperado = 0 if tel['estado'] == 'desativado' else 1
        if n != esperado:
            r['tokens_divergentes'] += 1
            _caso(conn, 'token_divergente', f'Telefone {tel["id"]} ({tel["estado"]}) tem {n} tokens ativos, esperado {esperado}',
                  {'tokens': n}, telefone_id=tel['id'], gravidade='alta')
        # 3. Estados x fatos
        if tel['estado'] in ('config_entregue', 'registrado', 'ativo', 'sem_registro') and tel['config_entregue_em'] is None:
            r['estados_sem_fato'] += 1
            _caso(conn, 'estado_sem_fato', f'Telefone {tel["id"]} em {tel["estado"]} sem config_entregue_em', {}, telefone_id=tel['id'])
        if tel['estado'] in ('registrado', 'ativo') and tel['registrado_em'] is None:
            r['estados_sem_fato'] += 1
            _caso(conn, 'estado_sem_fato', f'Telefone {tel["id"]} em {tel["estado"]} sem registrado_em', {}, telefone_id=tel['id'])
        if tel['estado'] in ('gdms_cadastrado', 'aguardando_boot') and tel['gdms_cadastrado_em'] is None:
            r['estados_sem_fato'] += 1
            _caso(conn, 'estado_sem_fato', f'Telefone {tel["id"]} em {tel["estado"]} sem gdms_cadastrado_em', {}, telefone_id=tel['id'])

    # 4. GDMS x banco
    if gdms_macs is not None:
        nossos = {t['mac']: t for t in conn.execute(select(db.telefones).where(and_(
            db.telefones.c.estado != 'desativado', db.telefones.c.gdms_cadastrado_em.isnot(None)))).mappings().all()}
        for mac in gdms_macs - set(nossos):
            r['gdms_orfaos'] += 1
            _caso(conn, 'gdms_orfao', f'MAC {mac} está no GDMS sem telefone ativo no banco', {'mac': mac}, gravidade='alta')
        for mac, t in nossos.items():
            if mac not in gdms_macs:
                r['gdms_faltando'] += 1
                _caso(conn, 'gdms_faltando', f'Telefone {t["id"]} marcado como cadastrado mas MAC {mac} não está no GDMS',
                      {'mac': mac}, telefone_id=t['id'], gravidade='alta')

    auditoria.registrar(conn, 'reconciliacao_executada', 'sistema', 'reconciliacao', detalhes=r)
    return r


def exportar_auditoria(conn, dia=None, destino='.'):
    """CSV do audit_log de um dia (UTC) + sha256. O hash deve ser guardado fora do servidor."""
    if dia:
        d0 = datetime.strptime(dia, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        d0 = (agora() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    d1 = d0 + timedelta(days=1)
    rows = conn.execute(select(db.audit_log).where(and_(db.audit_log.c.ts >= d0, db.audit_log.c.ts < d1))
                        .order_by(db.audit_log.c.id)).mappings().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = list(db.audit_log.c.keys())
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] if not isinstance(r[c], (dict, list)) else str(r[c]) for c in cols])
    conteudo = buf.getvalue().encode('utf-8')
    h = hashlib.sha256(conteudo).hexdigest()
    os.makedirs(destino, exist_ok=True)
    nome = f'audit_{d0.strftime("%Y-%m-%d")}.csv'
    caminho = os.path.join(destino, nome)
    with open(caminho, 'wb') as f:
        f.write(conteudo)
    with open(caminho + '.sha256', 'w') as f:
        f.write(f'{h}  {nome}\n')
    auditoria.registrar(conn, 'auditoria_exportada', 'sistema', 'export', detalhes={'arquivo': nome, 'linhas': len(rows), 'sha256': h})
    return {'arquivo': caminho, 'linhas': len(rows), 'sha256': h}


def funil(conn, dias=30):
    """Contagens para o painel da ONG."""
    desde = agora() - timedelta(days=dias)
    def cnt(acao):
        return conn.execute(select(func.count()).select_from(db.audit_log).where(and_(
            db.audit_log.c.acao == acao, db.audit_log.c.ts >= desde))).scalar()
    return [
        ('E1 contas criadas', cnt('conta_criada')),
        ('E2 crianças criadas', cnt('crianca_criada')),
        ('E3 telefones informados', cnt('telefone_dados_informados')),
        ('E4 GDMS ok', cnt('telefone_gdms_ok')),
        ('E5 prontos para ligar', cnt('telefone_config_enviada')),
        ('E7 config entregue', cnt('telefone_config_entregue')),
        ('E8 registrados', cnt('telefone_sip_registrado')),
        ('E9 primeira chamada', cnt('telefone_primeira_chamada')),
    ]
