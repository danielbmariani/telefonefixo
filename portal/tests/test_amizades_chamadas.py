"""Amizades por ID e decisao de chamada (logica do AGI)."""

from datetime import datetime

from sqlalchemy import text

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, acoes
from rede.servicos import chamadas, amizades, horarios
from rede.tempo import TZ_SP


def _duas_familias(client, app):
    cadastrar_e_entrar(client, app, email='a@x.com')
    ca = criar_crianca(client, 'ana01')
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='b@x.com')
    cb = criar_crianca(client, 'bia02')
    return ca, cb


def _login(client, app, email):
    client.get('/sair')
    from conftest import post as p
    p(client, '/entrar', email=email, senha='senha12345')


def test_pedido_aceite_e_permissao(client, app):
    ca, cb = _duas_familias(client, app)
    A, B = crianca_row(app, ca), crianca_row(app, cb)
    # B (logada) pede para A pelo ID
    r = post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'])
    assert r.status_code == 302
    with app.engine.begin() as c:
        assert not amizades.permitido(c, A['id_rede'], B['id_rede'])
        assert chamadas.decidir(c, B['id_rede'], A['id_rede'], datetime.now(TZ_SP))[0] == 'BLOCK_PERMISSION'
    assert any('quer ser amigo' in m['assunto'] for m in app.mailer.enviados if m['para'] == 'a@x.com')
    # A aceita
    _login(client, app, 'a@x.com')
    with app.engine.begin() as c:
        aid = c.execute(text('SELECT id FROM amizades')).scalar()
    post(client, f'/crianca/{ca}/contatos', acao='aceitar', amizade_id=aid)
    with app.engine.begin() as c:
        assert amizades.permitido(c, A['id_rede'], B['id_rede'])
        assert chamadas.decidir(c, A['id_rede'], B['id_rede'], datetime.now(TZ_SP)) == ('ALLOW', None)
        # 0 + ID (grupo do v1) nao existe mais: grupo e 0 + 1 digito, pelo servico rede-grupo (doc 16)
        assert chamadas.decidir(c, B['id_rede'], '0' + A['id_rede'], datetime.now(TZ_SP))[0] == 'BLOCK_UNKNOWN'
    a = acoes(app)
    assert 'pedido_amizade_enviado' in a and 'amizade_aceita' in a
    # tela lista o amigo
    r = client.get(f'/crianca/{ca}/contatos')
    assert b'bia02' in r.data


def test_bloqueio_silencioso(client, app):
    ca, cb = _duas_familias(client, app)
    A, B = crianca_row(app, ca), crianca_row(app, cb)
    post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'])
    _login(client, app, 'a@x.com')
    with app.engine.begin() as c:
        aid = c.execute(text('SELECT id FROM amizades')).scalar()
    post(client, f'/crianca/{ca}/contatos', acao='bloquear', amizade_id=aid)
    _login(client, app, 'b@x.com')
    emails_antes = len([m for m in app.mailer.enviados if m['para'] == 'a@x.com'])
    r = post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'], follow_redirects=True)
    assert b'Pedido enviado' in r.data   # mesma mensagem: nao revela o bloqueio
    assert len([m for m in app.mailer.enviados if m['para'] == 'a@x.com']) == emails_antes  # e nenhum e-mail sai
    with app.engine.begin() as c:
        assert not amizades.permitido(c, A['id_rede'], B['id_rede'])
        assert c.execute(text("SELECT count(*) FROM amizades WHERE estado='bloqueada'")).scalar() == 1


def test_id_inexistente_e_proprio(client, app):
    ca, cb = _duas_familias(client, app)
    B = crianca_row(app, cb)
    r = post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede='299999', follow_redirects=True)
    assert 'Não encontramos'.encode() in r.data
    r = post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=B['id_rede'], follow_redirects=True)
    assert 'própria'.encode() in r.data
    assert 'pedido_amizade_id_inexistente' in acoes(app)


def test_pedidos_cruzados_viram_aceite(client, app):
    ca, cb = _duas_familias(client, app)
    A, B = crianca_row(app, ca), crianca_row(app, cb)
    post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'])
    _login(client, app, 'a@x.com')
    post(client, f'/crianca/{ca}/contatos', acao='pedir', id_rede=B['id_rede'])
    with app.engine.begin() as c:
        assert amizades.permitido(c, A['id_rede'], B['id_rede'])


def test_decisao_horarios_e_desconhecidos(client, app):
    ca, cb = _duas_familias(client, app)
    A, B = crianca_row(app, ca), crianca_row(app, cb)
    with app.engine.begin() as c:
        a = amizades.pedir(c, B, A['id_rede'], B['familia_id'], app.cfg, mailer=app.mailer)
        amizades.responder(c, a['id'], A['familia_id'], 'aceitar')
        # horario de A: segunda 10:00-12:00 apenas
        horarios.salvar(c, A['id'], [{'inicio': '10:00', 'fim': '12:00', 'dias': [0]}], A['familia_id'])
        seg_11 = TZ_SP.localize(datetime(2026, 10, 26, 11, 0))   # segunda
        seg_15 = TZ_SP.localize(datetime(2026, 10, 26, 15, 0))
        ter_11 = TZ_SP.localize(datetime(2026, 10, 27, 11, 0))   # terca: sem horario = liberado
        assert chamadas.decidir(c, A['id_rede'], B['id_rede'], seg_11)[0] == 'ALLOW'
        assert chamadas.decidir(c, A['id_rede'], B['id_rede'], seg_15)[0] == 'BLOCK_SCHEDULE_CALLER'
        assert chamadas.decidir(c, B['id_rede'], A['id_rede'], seg_15)[0] == 'BLOCK_SCHEDULE_DEST'
        assert chamadas.decidir(c, A['id_rede'], B['id_rede'], ter_11)[0] == 'ALLOW'
        assert chamadas.decidir(c, A['id_rede'], '100', seg_15) == ('ALLOW', None)
        assert chamadas.decidir(c, A['id_rede'], '299999', ter_11)[0] == 'BLOCK_UNKNOWN'
        assert chamadas.decidir(c, '299999', A['id_rede'], ter_11)[0] == 'BLOCK_UNKNOWN'
        assert chamadas.decidir(c, A['id_rede'], '9' + B['id_rede'], ter_11)[0] == 'BLOCK_PERMISSION'   # 9 so com o proprio ID
        assert chamadas.decidir(c, A['id_rede'], '9' + A['id_rede'], ter_11)[0] == 'BLOCK_PARENT'       # sem celular cadastrado
        assert chamadas.decidir(c, A['id_rede'], '12', ter_11)[0] == 'BLOCK_UNKNOWN'
        bloqueios = c.execute(text("SELECT block_reason FROM call_logs WHERE status='BLOCKED'")).all()
    assert {'SCHEDULE_CALLER', 'SCHEDULE_DEST', 'UNKNOWN_DEST', 'CALLER_NOT_ACTIVATED', 'FAMILIA_NAO_CONFIGURADA'} <= {b[0] for b in bloqueios}


def test_horarios_via_http_e_historico(client, app):
    ca, cb = _duas_familias(client, app)
    r = post(client, f'/crianca/{cb}/horarios', pattern_count='1', start_h_0='10', start_m_0='00', end_h_0='18', end_m_0='30',
             days_0=['0', '1', '2'])
    assert r.status_code == 302
    with app.engine.begin() as c:
        rows = c.execute(text('SELECT dia_semana, inicio, fim FROM horarios ORDER BY dia_semana')).all()
    assert rows == [(0, '10:00', '18:30'), (1, '10:00', '18:30'), (2, '10:00', '18:30')]
    assert 'horarios_salvos' in acoes(app)
    assert client.get(f'/crianca/{cb}/historico').status_code == 200
    assert client.get(f'/crianca/{cb}/horarios').status_code == 200
    assert client.get(f'/crianca/{cb}/cartao').status_code == 200


def test_link_do_email_abre_pagina_so_com_o_pedido(client, app):
    ca, cb = _duas_familias(client, app)
    A = crianca_row(app, ca)
    post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'], mensagem='mae da bia, da escola')
    with app.engine.begin() as c:
        aid = c.execute(text('SELECT id FROM amizades')).scalar()
    corpo = [m['corpo'] for m in app.mailer.enviados if m['para'] == 'a@x.com'][-1]
    assert f'/crianca/{ca}/contatos/pedido/{aid}' in corpo
    # sem sessao, o link leva ao login e volta para a mesma pagina
    client.get('/sair')
    r = client.get(f'/crianca/{ca}/contatos/pedido/{aid}')
    assert r.status_code == 302 and r.headers['Location'] == f'/entrar?proximo=/crianca/{ca}/contatos/pedido/{aid}'
    r = post(client, '/entrar', email='a@x.com', senha='senha12345', proximo=f'/crianca/{ca}/contatos/pedido/{aid}')
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/crianca/{ca}/contatos/pedido/{aid}')
    html = client.get(f'/crianca/{ca}/contatos/pedido/{aid}').get_data(as_text=True)
    assert 'bia02' in html and 'mae da bia' in html and 'value="aceitar"' in html and 'value="recusar"' in html
    assert 'Aguardando a outra família' not in html   # so o pedido, sem o resto da pagina de amigos
    # a outra familia nao abre o pedido; endereco de fora do site nao vale como proximo
    r = post(client, '/entrar', email='b@x.com', senha='senha12345', proximo='https://outro.site/x')
    assert r.headers['Location'].endswith('/')
    _login(client, app, 'a@x.com')
    r = post(client, f'/crianca/{ca}/contatos', acao='aceitar', amizade_id=aid, follow_redirects=True)
    assert 'Amizade aceita' in r.get_data(as_text=True)
    assert 'já foi respondido' in client.get(f'/crianca/{ca}/contatos/pedido/{aid}').get_data(as_text=True)


def test_amigo_sem_telefone_aparece_avisado_e_fora_do_cartao(client, app):
    from conftest import MAC, SN
    ca, cb = _duas_familias(client, app)
    A = crianca_row(app, ca)
    post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=A['id_rede'])
    _login(client, app, 'a@x.com')
    with app.engine.begin() as c:
        aid = c.execute(text('SELECT id FROM amizades')).scalar()
    post(client, f'/crianca/{ca}/contatos', acao='aceitar', amizade_id=aid)
    html = client.get(f'/crianca/{ca}/contatos').get_data(as_text=True)
    assert 'bia02' in html and 'sem telefone na rede' in html and 'discar' not in html
    assert 'bia02' not in client.get(f'/crianca/{ca}/cartao').get_data(as_text=True)
    # bia ganha um telefone: volta a aparecer com o numero
    _login(client, app, 'b@x.com')
    post(client, f'/crianca/{cb}/telefone', acao='informar', mac=MAC, serial=SN)
    _login(client, app, 'a@x.com')
    html = client.get(f'/crianca/{ca}/contatos').get_data(as_text=True)
    assert 'sem telefone na rede' not in html and 'discar' in html
    assert 'bia02' in client.get(f'/crianca/{ca}/cartao').get_data(as_text=True)
