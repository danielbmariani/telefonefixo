"""
custos.py — Fase de teste do celular dos pais: o projeto paga, com teto por crianca por mes e um
disjuntor diario para a rede inteira (decisao do Daniel, 27/10/2026: R$ 5 por crianca).

O custo e estimado a partir de call_logs (duracao arredondada para cima ao minuto) com as tarifas em
cfg. A fatura real e da operadora; as tarifas aqui sao conservadoras. Quando a crianca chega ao teto,
9/8+ID e a entrada pelo celular param ate o mes virar, com mensagem no telefone. Avisos por e-mail
para ALERTA_EMAIL ao passar de ALERTA_FRACAO e ao esgotar.
"""

import math

from sqlalchemy import select, insert, text

from .. import db, auditoria
from ..tempo import agora, em_sp

SEGUNDOS_MINIMOS = 60   # abaixo disso, nem comeca a ligacao


def _saida(row):
    return len(row['callee_ext']) == 7 and row['callee_ext'][0] in '98'


def _entrada(row):
    return row['caller_ext'].isdigit() and len(row['caller_ext']) in (10, 11)


def custo_chamada(row, cfg):
    if row['status'] != 'ALLOWED' or not row['duration_seconds']:
        return 0.0
    minutos = math.ceil(row['duration_seconds'] / 60)
    if _saida(row):
        return minutos * cfg.TARIFA_SAIDA_MIN
    if _entrada(row):
        return minutos * cfg.TARIFA_ENTRADA_MIN
    return 0.0


def _rows(conn, cond, params):
    return conn.execute(text("SELECT caller_ext, callee_ext, status, duration_seconds FROM call_logs WHERE " + cond), params).mappings().all()


def gasto_crianca_mes(conn, id_rede, cfg, ref=None):
    mes = em_sp(ref or agora()).strftime('%Y-%m')
    rows = _rows(conn, "(caller_ext = :e OR callee_ext = :e OR callee_ext = :n OR callee_ext = :o) AND timestamp LIKE :m",
                 {'e': id_rede, 'n': '9' + id_rede, 'o': '8' + id_rede, 'm': mes + '%'})
    return round(sum(custo_chamada(r, cfg) for r in rows if _saida(r) or _entrada(r)), 2)


def gasto_rede_dia(conn, cfg, ref=None):
    dia = em_sp(ref or agora()).strftime('%Y-%m-%d')
    rows = _rows(conn, "timestamp LIKE :d", {'d': dia + '%'})
    return round(sum(custo_chamada(r, cfg) for r in rows), 2)


def segundos_permitidos(conn, cfg, id_rede, sentido='saida', ref=None):
    """Quanto tempo a ligacao pode durar sem furar os tetos. 0 = nao pode comecar."""
    tarifa = cfg.TARIFA_SAIDA_MIN if sentido == 'saida' else cfg.TARIFA_ENTRADA_MIN
    if tarifa <= 0:
        return 24 * 3600
    limites = []
    if cfg.TETO_CRIANCA_MES > 0:
        limites.append(cfg.TETO_CRIANCA_MES - gasto_crianca_mes(conn, id_rede, cfg, ref))
    if cfg.TETO_REDE_DIA > 0:
        limites.append(cfg.TETO_REDE_DIA - gasto_rede_dia(conn, cfg, ref))
    if not limites:
        return 24 * 3600
    restante = min(limites)
    segundos = int(round(restante / tarifa * 60))
    return segundos if segundos >= SEGUNDOS_MINIMOS else 0


def _ja_avisado(conn, chave):
    return conn.execute(select(db.alertas_custo.c.chave).where(db.alertas_custo.c.chave == chave)).first() is not None


def _marcar(conn, chave):
    conn.execute(insert(db.alertas_custo).values(chave=chave, ts=agora()))


def verificar_alertas(conn, cfg, mailer, ref=None):
    """Roda a cada minuto. Um e-mail por crianca ao passar de ALERTA_FRACAO do teto e outro ao esgotar;
    um por dia se a rede bater o disjuntor. Retorna quantos avisos saíram."""
    ref = ref or agora()
    mes = em_sp(ref).strftime('%Y-%m')
    dia = em_sp(ref).strftime('%Y-%m-%d')
    enviados = 0
    if cfg.TETO_CRIANCA_MES > 0:
        criancas = conn.execute(select(db.criancas.c.id, db.criancas.c.id_rede, db.criancas.c.apelido)
                                .where(db.criancas.c.ativa.is_(True))).mappings().all()
        for c in criancas:
            gasto = gasto_crianca_mes(conn, c['id_rede'], cfg, ref)
            for nivel, limiar in (('100', cfg.TETO_CRIANCA_MES), ('80', cfg.TETO_CRIANCA_MES * cfg.ALERTA_FRACAO)):
                if gasto >= limiar:
                    chave = f"crianca:{c['id']}:{mes}:{nivel}"
                    if not _ja_avisado(conn, chave):
                        _marcar(conn, chave)
                        if nivel == '100':
                            assunto = f"{c['apelido']} chegou ao teto de R$ {cfg.TETO_CRIANCA_MES:.2f} deste mês"
                            corpo = (f"{c['apelido']} (ID {c['id_rede']}) gastou R$ {gasto:.2f} em ligações com celular em {mes}. "
                                     f"As ligações com celular dessa criança ficam bloqueadas até o mês virar.\n\n"
                                     f"Para liberar, aumente REDE_TETO_CRIANCA_MES ou aguarde o próximo mês.")
                        else:
                            assunto = f"{c['apelido']} já usou {int(cfg.ALERTA_FRACAO * 100)}% do teto deste mês"
                            corpo = (f"{c['apelido']} (ID {c['id_rede']}) gastou R$ {gasto:.2f} de R$ {cfg.TETO_CRIANCA_MES:.2f} "
                                     f"em ligações com celular em {mes}.")
                        mailer.enviar(cfg.ALERTA_EMAIL, assunto, corpo)
                        auditoria.registrar(conn, 'teto_alerta_enviado', 'sistema', objeto_tipo='crianca', objeto_id=c['id'],
                                            detalhes={'nivel': nivel, 'mes': mes, 'gasto': gasto})
                        enviados += 1
                    break   # so o nivel mais alto atingido
    if cfg.TETO_REDE_DIA > 0:
        gasto = gasto_rede_dia(conn, cfg, ref)
        if gasto >= cfg.TETO_REDE_DIA:
            chave = f'rede:{dia}'
            if not _ja_avisado(conn, chave):
                _marcar(conn, chave)
                mailer.enviar(cfg.ALERTA_EMAIL, f'Rede chegou ao teto diário de R$ {cfg.TETO_REDE_DIA:.2f}',
                              f'As ligações com celular de toda a rede somaram R$ {gasto:.2f} em {dia} e foram pausadas até amanhã. '
                              f'Se não for uso normal, confira o histórico no painel da ONG.')
                auditoria.registrar(conn, 'teto_rede_alerta_enviado', 'sistema', detalhes={'dia': dia, 'gasto': gasto})
                enviados += 1
    return enviados
