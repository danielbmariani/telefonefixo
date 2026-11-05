"""Fase de teste do celular dos pais: teto por crianca, disjuntor da rede, avisos e mensagem no telefone."""

from datetime import timedelta

from sqlalchemy import insert, text

from rede import db
from rede.servicos import custos, chamadas, familia_telefones as fam
from rede.tempo import agora, em_sp
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post, acoes


def _hoje_15h():
    # as ligacoes de _lig entram com a hora de agora; a decisao precisa cair no mesmo mes (o teto e mensal)
    return em_sp(agora()).replace(hour=15, minute=0, second=0, microsecond=0)


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
        res, motivo = chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], _hoje_15h())
        assert res == 'ALLOW' and motivo == 'PJSIP/11987654321@nvoip;limite=860'
    # esgota: 14 ligacoes de 1 min = R$ 4,20 (total 4,90) -> sobra R$ 0,10 = 20 s < 60 s -> bloqueia
    for _ in range(14):
        _lig(app, cr['id_rede'], '9' + cr['id_rede'], 60)
    with app.engine.begin() as c:
        assert custos.gasto_crianca_mes(c, cr['id_rede'], cfg) == 4.90
        assert custos.segundos_permitidos(c, cfg, cr['id_rede'], 'saida') == 0
        t = _hoje_15h()
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
    html = r.get_data(as_text=True)
    # em minutos, sem dinheiro: 1 min usado; do teto de R$ 5 sobram R$ 4,70, que dao 15 min para o celular
    assert 'Fase de teste' in html and 'ana01: usou 1 min, restam cerca de 15 min' in html
    assert 'R$' not in html and 'custo' not in html and 'paga' not in html
    r = client.get('/termos')
    assert b'2026-10-' in r.data and b'fase de teste' in r.data


def test_orcamento_mensal_da_rede_nunca_e_ultrapassado(client, app):
    # duas familias, uma crianca com celular em cada: o orcamento da rede e dividido entre as duas
    cadastrar_e_entrar(client, app)
    a = crianca_row(app, criar_crianca(client, 'ana01'))
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='pai@x.com')
    b = crianca_row(app, criar_crianca(client, 'beto02'))
    sem = crianca_row(app, criar_crianca(client, 'caio03'))   # mesma familia de beto: tambem conta
    cfg = app.cfg
    with app.engine.begin() as c:
        assert custos.criancas_com_celular(c) == 0
        assert custos.teto_crianca(c, cfg) == 5.0             # sem ninguem com celular, vale o teto por crianca
        fam.adicionar(c, a['familia_id'], '11987654321', 'Mãe')
        fam.adicionar(c, b['familia_id'], '11911111111', 'Pai')
        assert custos.criancas_com_celular(c) == 3
        assert custos.teto_crianca(c, cfg) == 5.0             # 450 / 3 e bem mais que 5
    cfg.TETO_REDE_MES = 10.0
    try:
        with app.engine.begin() as c:
            assert custos.teto_crianca(c, cfg) == 3.33        # 10 / 3, arredondado para baixo
        for _ in range(10):
            _lig(app, a['id_rede'], '9' + a['id_rede'], 60)   # ana: R$ 3,00
        with app.engine.begin() as c:
            assert custos.gasto_rede_mes(c, cfg) == 3.0
            assert custos.segundos_permitidos(c, cfg, a['id_rede'], 'saida') == 66   # sobram R$ 0,33
            assert custos.segundos_permitidos(c, cfg, b['id_rede'], 'saida') == 666  # beto ainda tem a parte dele
        _lig(app, a['id_rede'], '9' + a['id_rede'], 60)       # ana: R$ 3,30
        with app.engine.begin() as c, app.app_context():      # decidir le a config da aplicacao
            assert custos.segundos_permitidos(c, cfg, a['id_rede'], 'saida') == 0
            assert chamadas.decidir(c, a['id_rede'], '9' + a['id_rede'], _hoje_15h()) == ('BLOCK_TETO', 'TETO')
        # mesmo que as tres gastem tudo, a soma fica abaixo do orcamento
        with app.engine.begin() as c:
            assert custos.teto_crianca(c, cfg) * custos.criancas_com_celular(c) <= cfg.TETO_REDE_MES
    finally:
        cfg.TETO_REDE_MES = 450.0


def test_aviso_do_orcamento_mensal_e_resumo_do_painel(client, app):
    cadastrar_e_entrar(client, app)
    a = crianca_row(app, criar_crianca(client, 'ana01'))
    cfg = app.cfg
    with app.engine.begin() as c:
        fam.adicionar(c, a['familia_id'], '11987654321', 'Mãe')
    _lig(app, a['id_rede'], '9' + a['id_rede'], 61)            # 2 min para o celular = R$ 0,60
    _lig(app, '11987654321', a['id_rede'], 120)                # 2 min do celular = R$ 0,10
    _lig(app, a['id_rede'], '9' + a['id_rede'], 0, status='NOANSWER')
    _lig(app, a['id_rede'], '234567', 600)                     # entre criancas: nao conta
    with app.engine.begin() as c:
        r = custos.resumo_mes(c, cfg)
    assert r['gasto'] == 0.70 and r['teto_rede'] == 450.0 and r['pct'] == 0 and r['criancas_com_celular'] == 1
    assert r['linhas'] == [{'apelido': 'ana01', 'id_rede': a['id_rede'], 'ligacoes': 2, 'min_saida': 2, 'min_entrada': 2, 'gasto': 0.70}]
    assert r['projecao'] >= r['gasto']
    cfg.TETO_REDE_MES = 0.80
    try:
        with app.engine.begin() as c:
            assert custos.verificar_alertas(c, cfg, app.mailer) >= 1     # 0,70 de 0,80: passou de 80%
        m = app.mailer.ultimo_para(cfg.ALERTA_EMAIL)
        assert '80%' in m['assunto'] and 'orçamento mensal' in m['assunto']
        with app.engine.begin() as c:
            assert custos.verificar_alertas(c, cfg, app.mailer) == 0     # nao repete
        _lig(app, a['id_rede'], '9' + a['id_rede'], 30)                  # R$ 1,00 no total
        with app.engine.begin() as c:
            assert custos.verificar_alertas(c, cfg, app.mailer) >= 1
            assert custos.segundos_permitidos(c, cfg, a['id_rede'], 'saida') == 0
        assert 'chegou ao orçamento mensal' in app.mailer.ultimo_para(cfg.ALERTA_EMAIL)['assunto']
        assert 'teto_rede_mes_alerta_enviado' in acoes(app)
    finally:
        cfg.TETO_REDE_MES = 450.0


def test_painel_mostra_o_gasto_com_celular(client, app):
    from rede.servicos import contas
    cadastrar_e_entrar(client, app)
    a = crianca_row(app, criar_crianca(client, 'ana01'))
    with app.engine.begin() as c:
        fam.adicionar(c, a['familia_id'], '11987654321', 'Mãe')
        contas.criar_operador(c, 'op@x.com', 'senha12345', 'Op', 'operador')
    _lig(app, a['id_rede'], '9' + a['id_rede'], 61)
    client.get('/sair')
    r = post(client, '/entrar', email='op@x.com', senha='senha12345')
    assert r.status_code == 302, r.data
    html = client.get('/ong/').get_data(as_text=True)
    assert 'Celulares em' in html and 'R$ 0.60' in html and 'de R$ 450.00' in html and 'ana01' in html
