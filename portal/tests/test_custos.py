"""Fase de teste do celular dos pais: teto por crianca, disjuntor da rede, avisos e mensagem no telefone."""

from datetime import timedelta

from sqlalchemy import insert, text

from rede import db
from rede.servicos import custos, chamadas, familia_telefones as fam
from rede.tempo import agora, em_sp, TZ_SP
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post, acoes


def _lig(app, de, para, dur, quando=None, status='ALLOWED'):
    ts = em_sp(quando or agora()).strftime('%Y-%m-%d %H:%M:%S')
    with app.engine.begin() as c:
        c.execute(insert(db.call_logs).values(caller_ext=de, callee_ext=para, timestamp=ts, status=status, duration_seconds=dur))


def _ativar_telefone(app, cid):
    with app.engine.begin() as c:
        c.execute(insert(db.telefones).values(crianca_id=cid, mac='C074AD010203', serial='SN1', modelo='grp', estado='ativo',
                                              admin_senha='x', informado_em=agora()))


def test_custo_e_teto_por_crianca(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01'); cr = crianca_row(app, cid)
    cfg = app.cfg
    assert (cfg.TETO_CRIANCA_MES, cfg.TARIFA_SAIDA_MIN, cfg.TARIFA_ENTRADA_MIN) == (5.0, 0.30, 0.05)
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        assert custos.gasto_crianca_mes(c, cr['id_rede'], cfg) == 0
        assert custos.segundos_permitidos(c, cfg, cr['id_rede'], 'saida') == 1000   # 5,00 / 0,30 * 60
    _lig(app, cr['id_rede'], '9' + cr['id_rede'], 61)                 # 2 min cobrados = R$ 0,60
    _lig(app, '11987654321', cr['id_rede'], 120)                      # 2 min entrada = R$ 0,10
    _lig(app, cr['id_rede'], '234567', 600)                           # entre criancas: nao conta
    _lig(app, cr['id_rede'], '9' + cr['id_rede'], 0, status='BLOCKED')
    with app.engine.begin() as c:
        assert custos.gasto_crianca_mes(c, cr['id_rede'], cfg) == 0.70
        assert custos.segundos_permitidos(c, cfg, cr['id_rede'], 'saida') == 860
        res, motivo = chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], TZ_SP.localize(__import__('datetime').datetime(2026, 10, 27, 15, 0)))
        assert res == 'ALLOW' and motivo == 'PJSIP/11987654321@nvoip;limite=860'
    # esgota: 14 ligacoes de 1 min = R$ 4,20 (total 4,90) -> sobra R$ 0,10 = 20 s < 60 s -> bloqueia
    for _ in range(14):
        _lig(app, cr['id_rede'], '9' + cr['id_rede'], 60)
    with app.engine.begin() as c:
        assert custos.gasto_crianca_mes(c, cr['id_rede'], cfg) == 4.90
        assert custos.segundos_permitidos(c, cfg, cr['id_rede'], 'saida') == 0
        t = TZ_SP.localize(__import__('datetime').datetime(2026, 10, 27, 15, 0))
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], t) == ('BLOCK_TETO', 'TETO')
    # entrada: tarifa menor, ainda cabem 120 s
    _ativar_telefone(app, cid)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '11987654321', t)
        assert res == 'ALLOW' and d['limite_s'] == 120
    # mes que vem zera
    with app.engine.begin() as c:
        prox = agora() + timedelta(days=35)
        assert custos.gasto_crianca_mes(c, cr['id_rede'], cfg, prox) == 0


def test_disjuntor_da_rede_e_avisos(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01'); cr = crianca_row(app, cid)
    cid2 = criar_crianca(client, 'bia02'); cr2 = crianca_row(app, cid2)
    cfg = app.cfg
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        assert custos.verificar_alertas(c, cfg, app.mailer) == 0
    # ana gasta R$ 4,20 (84%): aviso de 80%, uma vez so
    for _ in range(14):
        _lig(app, cr['id_rede'], '9' + cr['id_rede'], 60)
    with app.engine.begin() as c:
        assert custos.verificar_alertas(c, cfg, app.mailer) == 1
        assert custos.verificar_alertas(c, cfg, app.mailer) == 0
    m = app.mailer.ultimo_para(cfg.ALERTA_EMAIL)
    assert '80%' in m['assunto'] and 'ana01' in m['assunto'] and 'R$ 4.20' in m['corpo'].replace(',', '.')
    # chega a 100%: segundo aviso
    for _ in range(3):
        _lig(app, cr['id_rede'], '9' + cr['id_rede'], 60)
    with app.engine.begin() as c:
        assert custos.verificar_alertas(c, cfg, app.mailer) == 1
    assert 'teto' in app.mailer.ultimo_para(cfg.ALERTA_EMAIL)['assunto']
    # disjuntor da rede: R$ 20 no dia bloqueia ate quem nao gastou nada
    for _ in range(50):
        _lig(app, cr2['id_rede'], '9' + cr2['id_rede'], 60)   # bia: R$ 15 (acima do teto dela tambem)
    with app.engine.begin() as c:
        assert custos.gasto_rede_dia(c, cfg) >= 20.0
        c.execute(text("UPDATE call_logs SET callee_ext = '9' || :n WHERE callee_ext = :o"), {'n': '345678', 'o': '9' + cr2['id_rede']})
        cid3 = None
    cid3 = criar_crianca(client, 'caio03'); cr3 = crianca_row(app, cid3)
    with app.engine.begin() as c:
        fam.adicionar(c, cr3['familia_id'], '11911111111', 'Pai')
        assert custos.gasto_crianca_mes(c, cr3['id_rede'], cfg) == 0
        assert custos.segundos_permitidos(c, cfg, cr3['id_rede'], 'saida') == 0   # rede estourou o dia
        n = custos.verificar_alertas(c, cfg, app.mailer)
        assert n >= 1
    assert 'teto diário' in app.mailer.ultimo_para(cfg.ALERTA_EMAIL)['assunto']
    acs = acoes(app)
    assert 'teto_alerta_enviado' in acs and 'teto_rede_alerta_enviado' in acs


def test_pagina_celulares_mostra_fase_de_teste(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01'); cr = crianca_row(app, cid)
    _lig(app, cr['id_rede'], '9' + cr['id_rede'], 60)
    r = client.get('/celulares')
    assert b'Fase de teste' in r.data and b'R$ 5.00' in r.data and b'ana01: R$ 0.30' in r.data
    r = client.get('/termos')
    assert b'2026-10-' in r.data and b'fase de teste' in r.data
