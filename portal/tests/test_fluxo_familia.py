"""Fluxo E1-E3 pelo HTTP, com auditoria."""

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, telefone_row, acoes, MAC, SN


def test_cadastro_verificacao_consentimento_e_auditoria(client, app):
    cadastrar_e_entrar(client, app)
    a = acoes(app)
    for esperado in ('cadastro_iniciado', 'conta_criada', 'email_verificado', 'consentimento_termos',
                     'consentimento_privacidade', 'consentimento_crianca'):
        assert esperado in a, a
    # consentimento guarda versao e hash do texto
    from sqlalchemy import text
    with app.engine.begin() as c:
        rows = c.execute(text('SELECT tipo, versao, hash_texto FROM consentimentos')).all()
    assert len(rows) == 3 and all(len(h) == 64 for _, _, h in rows)


def test_codigo_errado_e_limite(client, app):
    post(client, '/cadastrar', email='a@x.com', senha='senha12345', senha2='senha12345', nome='A')
    for _ in range(3):
        r = post(client, '/verificar-email', codigo='000000')
        assert r.status_code == 200
    assert 'codigo_email_incorreto' in acoes(app)


def test_senha_curta_e_emails_invalidos(client, app):
    r = post(client, '/cadastrar', email='nao-e-email', senha='senha12345', senha2='senha12345', nome='A')
    assert b'inv' in r.data
    r = post(client, '/cadastrar', email='a@x.com', senha='curta', senha2='curta', nome='A')
    assert b'8 caracteres' in r.data


def test_crianca_cria_ramal_e_id(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'jose07')
    c = crianca_row(app, cid)
    assert c['apelido'] == 'jose07'
    assert c['id_rede'][0] in '234567' and len(c['id_rede']) == 6
    from sqlalchemy import text
    with app.engine.begin() as conn:
        e = conn.execute(text('SELECT callerid, context FROM ps_endpoints WHERE id=:i'), {'i': c['id_rede']}).first()
        au = conn.execute(text('SELECT password FROM ps_auths WHERE id=:i'), {'i': c['id_rede']}).first()
        ao = conn.execute(text('SELECT max_contacts FROM ps_aors WHERE id=:i'), {'i': c['id_rede']}).first()
    assert e[0] == f'jose07 <{c["id_rede"]}>' and e[1] == 'telefones-criancas'
    assert au[0] == c['senha_sip'] and ao[0] == 1
    a = acoes(app, 'crianca', cid)
    assert 'crianca_criada' in a and 'ramal_criado' in a


def test_apelido_invalido_registrado(client, app):
    cadastrar_e_entrar(client, app)
    r = post(client, '/crianca/nova', apelido='Ana Silva')
    assert r.status_code == 200
    assert 'apelido_rejeitado' in acoes(app)


def test_e3_informar_mac_cria_telefone_token_e_fila_simulada(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    r = post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN, loja='Kabum')
    assert r.status_code == 302
    t = telefone_row(app, cid)
    assert t['mac'] == 'C074AD010203' and t['serial'] == SN and t['loja'] == 'Kabum'
    # GDMS simulado: ja passou por gdms_ok e rps_ok -> aguardando_boot
    assert t['estado'] == 'aguardando_boot'
    assert t['gdms_cadastrado_em'] is not None and t['config_enviada_em'] is not None
    a = acoes(app, 'telefone', t['id'])
    assert a[:3] == ['telefone_dados_informados', 'telefone_gdms_ok', 'telefone_config_enviada']
    from sqlalchemy import text
    with app.engine.begin() as c:
        hist = c.execute(text('SELECT de, para, evento FROM device_state_history WHERE telefone_id=:t ORDER BY id'), {'t': t['id']}).all()
        tok = c.execute(text('SELECT count(*) FROM prov_tokens WHERE telefone_id=:t AND ativo=1'), {'t': t['id']}).scalar()
        glog = c.execute(text('SELECT metodo, ret_code FROM gdms_log WHERE telefone_id=:t'), {'t': t['id']}).all()
    assert [h[2] for h in hist] == ['dados_informados', 'gdms_ok', 'config_enviada']
    assert hist[0][0] is None and hist[-1][1] == 'aguardando_boot'
    assert tok == 1
    assert glog == [('SIMULADO', 0)]
    # e-mail "pode ligar o telefone"
    assert any('pode ligar' in m['assunto'].lower() for m in app.mailer.enviados)


def test_e3_mac_invalido_e_nao_grandstream(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac='00:11:22:33:44:55', serial=SN)
    assert telefone_row(app, cid) is None
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac='zz', serial=SN)
    a = acoes(app)
    assert a.count('telefone_dados_rejeitados') == 2


def test_e3_mac_duplicado_entre_familias_abre_caso_sem_sobrescrever(client, app):
    cadastrar_e_entrar(client, app, email='a@x.com')
    cid = criar_crianca(client, 'ana01')
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='b@x.com')
    cid2 = criar_crianca(client, 'bia02')
    r = post(client, f'/crianca/{cid2}/telefone', acao='informar', mac=MAC, serial=SN)
    assert r.status_code == 302
    assert telefone_row(app, cid2) is None
    assert telefone_row(app, cid)['estado'] != 'desativado'
    from sqlalchemy import text
    with app.engine.begin() as c:
        casos = c.execute(text("SELECT tipo, gravidade FROM casos")).all()
    assert ('mac_duplicado', 'alta') in casos
    assert 'alerta_mac_duplicado' in acoes(app)


def test_troca_de_aparelho_desativa_anterior(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    t1 = telefone_row(app, cid)
    post(client, f'/crianca/{cid}/telefone', acao='remover')
    assert telefone_row(app, cid) is None
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac='C0:74:AD:AA:BB:CC', serial='SN999999ZZ')
    t2 = telefone_row(app, cid)
    assert t2['id'] != t1['id']
    from rede.servicos import telefones
    with app.engine.begin() as c:
        assert telefones.por_id(c, t1['id'])['estado'] == 'desativado'
        assert telefones.token_ativo(c, t1['id']) is None


def test_status_json_e_informou_ligado(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    s = client.get(f'/crianca/{cid}/telefone/status.json').get_json()
    assert s['estado'] == 'aguardando_boot' and s['pode_informar_ligado'] is True
    post(client, f'/crianca/{cid}/telefone', acao='liguei')
    assert telefone_row(app, cid)['familia_ligou_em'] is not None
    assert 'familia_informou_ligado' in acoes(app)


def test_outra_familia_nao_acessa_crianca(client, app):
    cadastrar_e_entrar(client, app, email='a@x.com')
    cid = criar_crianca(client, 'ana01')
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='b@x.com')
    assert client.get(f'/crianca/{cid}/telefone').status_code == 404
    assert client.get(f'/crianca/{cid}/contatos').status_code == 404


def test_csrf_obrigatorio(client, app):
    r = client.post('/entrar', data={'email': 'a@x.com', 'senha': 'x'})
    assert r.status_code == 403


def test_pagina_inicial_publica_e_reenvio_de_codigo(client, app):
    import re
    r = client.get('/')
    assert r.status_code == 200 and 'adiar o celular sem isolar' in r.get_data(as_text=True)
    assert 'Criar a conta da fam' not in r.get_data(as_text=True)  # botao grande saiu do topo (27/10)
    # reenvio sem cadastro em andamento -> volta ao cadastro
    r = post(client, '/reenviar-codigo')
    assert r.status_code == 302 and r.headers['Location'].endswith('/cadastrar')
    post(client, '/cadastrar', email='re@x.com', senha='senha12345', senha2='senha12345', nome='Re')
    antigo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('re@x.com')['corpo']).group(1)
    r = post(client, '/reenviar-codigo')
    assert r.status_code == 302 and r.headers['Location'].endswith('/verificar-email')
    novo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('re@x.com')['corpo']).group(1)
    assert 'novo código' in app.mailer.ultimo_para('re@x.com')['assunto']
    # o codigo antigo nao vale mais; o novo entra
    r = post(client, '/verificar-email', codigo=antigo)
    assert r.status_code == 200
    r = post(client, '/verificar-email', codigo=novo)
    assert r.status_code == 302
    # limite de 3 por hora (1 original + reenvios)
    post(client, '/cadastrar', email='lim@x.com', senha='senha12345', senha2='senha12345', nome='L')
    post(client, '/reenviar-codigo'); post(client, '/reenviar-codigo')
    n = len([m for m in app.mailer.enviados if m['para'] == 'lim@x.com'])
    post(client, '/reenviar-codigo')
    assert len([m for m in app.mailer.enviados if m['para'] == 'lim@x.com']) == n == 3
    # logado, '/' nao mostra a pagina publica
    cadastrar_e_entrar(client, app, email='log@x.com')
    r = client.get('/')
    assert r.status_code == 302


def test_pedido_de_amizade_leva_mensagem_de_apresentacao(client, app):
    cadastrar_e_entrar(client, app, email='a@x.com')
    ca = criar_crianca(client, 'anaclara')
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='b@x.com')
    cb = criar_crianca(client, 'beto')
    id_a = crianca_row(app, ca)['id_rede']
    r = post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=id_a, mensagem='  Beto, da  4ª série da Escola X ')
    assert r.status_code == 302
    m = app.mailer.ultimo_para('a@x.com')
    assert 'Quem está pedindo: "Beto, da 4ª série da Escola X"' in m['corpo']
    # mensagem longa demais e recusada
    r = post(client, f'/crianca/{cb}/contatos', follow_redirects=True, acao='pedir', id_rede='234567', mensagem='x' * 81)
    assert 'no máximo 80' in r.data.decode()
    client.get('/sair')
    post(client, '/entrar', email='a@x.com', senha='senha12345')
    r = client.get(f'/crianca/{ca}/contatos')
    assert 'Beto, da 4ª série da Escola X' in r.data.decode()


def test_migrar_acrescenta_coluna_nova(app):
    from sqlalchemy import text, inspect
    from rede import db
    with app.engine.begin() as c:
        c.execute(text('ALTER TABLE amizades DROP COLUMN mensagem'))
    assert 'mensagem' not in {col['name'] for col in inspect(app.engine).get_columns('amizades')}
    assert db.migrar(app.engine) == [('amizades', 'mensagem')]
    assert 'mensagem' in {col['name'] for col in inspect(app.engine).get_columns('amizades')}
    assert db.migrar(app.engine) == []


def test_silenciar_agora_bloqueia_e_reativa(client, app):
    from datetime import datetime
    from rede.servicos import horarios
    from rede.tempo import TZ_SP
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    c = crianca_row(app, cid)
    with app.engine.begin() as conn:
        assert horarios.dentro_do_horario(conn, c['id_rede'], datetime.now(TZ_SP))
    r = post(client, f'/crianca/{cid}/horarios', follow_redirects=True, acao='silenciar', duracao='2h')
    assert 'silenciado até' in r.data.decode()
    with app.engine.begin() as conn:
        assert not horarios.dentro_do_horario(conn, c['id_rede'], datetime.now(TZ_SP))
    r = post(client, f'/crianca/{cid}/horarios', follow_redirects=True, acao='reativar')
    assert 'reativado' in r.data.decode()
    with app.engine.begin() as conn:
        assert horarios.dentro_do_horario(conn, c['id_rede'], datetime.now(TZ_SP))
    a = acoes(app, 'crianca', cid)
    assert 'silencio_ligado' in a and 'silencio_desligado' in a


def test_para_retornar_e_teclas_rapidas(client, app):
    from sqlalchemy import text
    from rede.servicos import historico
    cadastrar_e_entrar(client, app)
    ca = criar_crianca(client, 'anaclara')
    cb = criar_crianca(client, 'beto')
    id_a, id_b = crianca_row(app, ca)['id_rede'], crianca_row(app, cb)['id_rede']
    # beto ligou para anaclara duas vezes sem resposta; depois anaclara ligou para beto e conversaram
    with app.engine.begin() as conn:
        for ts, st, dur in (('2026-10-26 10:00:00', 'NOANSWER', None), ('2026-10-26 10:05:00', 'CANCEL', None)):
            conn.execute(text("INSERT INTO call_logs (caller_ext, callee_ext, timestamp, status, duration_seconds) VALUES (:a, :b, :t, :s, :d)"),
                         {'a': id_b, 'b': id_a, 't': ts, 's': st, 'd': dur})
        from datetime import datetime, timedelta
        from rede.tempo import TZ_SP
        recente = (datetime.now(TZ_SP) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(text("UPDATE call_logs SET timestamp=:t"), {'t': recente})
        r = historico.para_retornar(conn, id_a)
        assert len(r) == 1 and r[0]['contato'] == id_b and r[0]['vezes'] == 2
        assert historico.para_retornar(conn, id_b) == []
        conn.execute(text("INSERT INTO call_logs (caller_ext, callee_ext, timestamp, status, duration_seconds) VALUES (:a, :b, :t, 'ALLOWED', 30)"),
                     {'a': id_a, 'b': id_b, 't': (datetime.now(TZ_SP)).strftime('%Y-%m-%d %H:%M:%S')})
        assert historico.para_retornar(conn, id_a) == []
    # amizade aceita -> tecla rapida no cfg do telefone de anaclara
    post(client, f'/crianca/{cb}/contatos', acao='pedir', id_rede=id_a)
    with app.engine.begin() as conn:
        aid = conn.execute(text('SELECT id FROM amizades')).scalar()
    post(client, f'/crianca/{ca}/contatos', acao='aceitar', amizade_id=aid)
    post(client, f'/crianca/{ca}/telefone', acao='informar', mac=MAC, serial=SN)
    with app.engine.begin() as conn:
        tok = conn.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=(SELECT id FROM telefones WHERE crianca_id=:c)'), {'c': ca}).scalar()
    cfg = client.get(f'/p/{tok}/cfgc074ad010203.xml').data.decode()
    assert f'<P1468>{id_b}</P1468>' in cfg and '<P1467>beto</P1467>' in cfg and '<P1365>0</P1365>' in cfg


def test_turma_codigo_aceite_e_pedidos_em_lote(client, app):
    from sqlalchemy import text
    # familia A cria a turma com anaclara
    cadastrar_e_entrar(client, app, email='a@x.com')
    ca = criar_crianca(client, 'anaclara')
    r = post(client, f'/crianca/{ca}/turmas', follow_redirects=True, acao='criar', nome='4º ano B')
    html = r.data.decode()
    assert '4º ano B' in html and 'criada. Passe o código' in html
    with app.engine.begin() as conn:
        t = conn.execute(text('SELECT id, codigo FROM turmas')).mappings().first()
    assert len(t['codigo']) == 6 and not set(t['codigo']) & set('IO01')
    client.get('/sair')
    # familia B entra pelo codigo (minusculo e com espaco: normaliza)
    cadastrar_e_entrar(client, app, email='b@x.com')
    cb = criar_crianca(client, 'beto')
    r = post(client, f'/crianca/{cb}/turmas', follow_redirects=True, acao='entrar', codigo=t['codigo'][:3].lower() + ' ' + t['codigo'][3:])
    assert 'Pedido enviado para a turma' in r.data.decode()
    assert 'quer entrar na turma 4º ano B' in app.mailer.ultimo_para('a@x.com')['assunto']
    r = post(client, f'/crianca/{cb}/turmas', follow_redirects=True, acao='entrar', codigo='ZZZZZZ')
    assert 'não encontrado' in r.data.decode()
    # beto nao ve a turma de A ate ser aceito? ve como pendente
    r = client.get(f'/crianca/{cb}/turmas')
    assert 'aguardando quem administra' in r.data.decode()
    client.get('/sair')
    # familia A aceita: beto pede amizade a anaclara automaticamente, com apresentacao da turma
    post(client, '/entrar', email='a@x.com', senha='senha12345')
    with app.engine.begin() as conn:
        mid = conn.execute(text("SELECT id FROM turma_membros WHERE estado='pendente'")).scalar()
    r = post(client, f'/crianca/{ca}/turma/{t["id"]}', follow_redirects=True, acao='aceitar', membro_id=mid)
    assert 'Entrada aceita' in r.data.decode()
    with app.engine.begin() as conn:
        am = conn.execute(text('SELECT estado, mensagem FROM amizades')).mappings().all()
    assert len(am) == 1 and am[0]['estado'] == 'pendente' and am[0]['mensagem'] == 'da turma 4º ano B'
    # na tela da turma, anaclara ve beto com botao de aceitar amizade; aceita
    r = client.get(f'/crianca/{ca}/turma/{t["id"]}')
    assert 'Aceitar amizade' in r.data.decode() and 'beto' in r.data.decode()
    with app.engine.begin() as conn:
        aid = conn.execute(text('SELECT id FROM amizades')).scalar()
    post(client, f'/crianca/{ca}/turma/{t["id"]}', acao='aceitar_amizade', amizade_id=aid)
    r = client.get(f'/crianca/{ca}/turma/{t["id"]}')
    assert '>amigos<' in r.data.decode()
    # familia C nao pode abrir a turma sem estar nela
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='c@x.com')
    cc = criar_crianca(client, 'carla')
    assert client.get(f'/crianca/{cc}/turma/{t["id"]}').status_code == 404
    # link do e-mail leva o administrador para a turma
    client.get('/sair')
    post(client, '/entrar', email='a@x.com', senha='senha12345')
    r = client.get(f'/turma/{t["id"]}')
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/crianca/{ca}/turma/{t["id"]}')

