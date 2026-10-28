"""Painel da ONG (consulta de auditoria registrada), exclusao de conta, login/reset."""

import re

from sqlalchemy import text

from conftest import post, csrf, cadastrar_e_entrar, criar_crianca, crianca_row, telefone_row, acoes, MAC, SN
from rede.servicos import contas


def _operador(client, app):
    with app.engine.begin() as c:
        contas.criar_operador(c, 'op@ong.org', 'senha12345', 'Op')
    client.get('/sair')
    post(client, '/entrar', email='op@ong.org', senha='senha12345')


def test_familia_nao_acessa_ong(client, app):
    cadastrar_e_entrar(client, app)
    assert client.get('/ong/').status_code == 403


def test_painel_casos_tarefas_e_consulta_registrada(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    t = telefone_row(app, cid)
    _operador(client, app)
    assert client.get('/ong/').status_code == 200
    assert client.get('/ong/casos').status_code == 200
    assert client.get('/ong/tarefas').status_code == 200
    r = client.get(f'/ong/telefone/{t["id"]}')
    assert r.status_code == 200 and b'dados_informados' in r.data
    r = client.get('/ong/auditoria?acao=telefone_gdms_ok')
    assert r.status_code == 200 and b'telefone_gdms_ok' in r.data
    r = client.get(f'/ong/telefones?q={MAC}')
    assert r.status_code == 200 and MAC.replace(':', '').encode() in r.data
    a = acoes(app)
    assert a.count('auditoria_consultada') >= 2 and 'telefones_pesquisados' in a
    with app.engine.begin() as c:
        quem = c.execute(text("SELECT DISTINCT ator_id FROM audit_log WHERE acao='auditoria_consultada'")).all()
    assert quem == [('op@ong.org',)]


def test_resolver_caso_exige_motivo(client, app):
    cadastrar_e_entrar(client, app, email='a@x.com')
    ca = criar_crianca(client, 'ana01')
    post(client, f'/crianca/{ca}/telefone', acao='informar', mac=MAC, serial=SN)
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='b@x.com')
    cb = criar_crianca(client, 'bia02')
    post(client, f'/crianca/{cb}/telefone', acao='informar', mac=MAC, serial=SN)   # abre caso mac_duplicado
    _operador(client, app)
    with app.engine.begin() as c:
        cid = c.execute(text("SELECT id FROM casos WHERE tipo='mac_duplicado'")).scalar()
    post(client, '/ong/casos', caso_id=cid, motivo='')
    with app.engine.begin() as c:
        assert c.execute(text('SELECT estado FROM casos WHERE id=:i'), {'i': cid}).scalar() == 'aberto'
    post(client, '/ong/casos', caso_id=cid, motivo='familia B digitou MAC errado; orientada por e-mail')
    with app.engine.begin() as c:
        row = c.execute(text('SELECT estado, resolvido_por FROM casos WHERE id=:i'), {'i': cid}).first()
    assert row == ('resolvido', 'op@ong.org')
    assert 'caso_resolvido' in acoes(app)


def test_excluir_conta_cascata(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    c0 = crianca_row(app, cid)
    r = post(client, '/excluir-conta', confirmacao='nao')
    assert r.status_code == 200
    r = post(client, '/excluir-conta', confirmacao='EXCLUIR')
    assert r.status_code == 302
    with app.engine.begin() as c:
        assert c.execute(text('SELECT count(*) FROM ps_endpoints WHERE id=:i'), {'i': c0['id_rede']}).scalar() == 0
        assert c.execute(text('SELECT count(*) FROM prov_tokens WHERE ativo=1')).scalar() == 0
        fam = c.execute(text('SELECT email, suspensa FROM familias')).first()
        tel = c.execute(text('SELECT estado FROM telefones')).scalar()
        fila = c.execute(text("SELECT etapa, estado FROM gdms_fila ORDER BY id DESC LIMIT 1")).first()
    assert fam[0].startswith('excluida-') and fam[1] == 1
    assert tel == 'desativado' and tuple(fila) == ('zerar', 'pendente')   # zera e tira do GDMS pela fila, nao por operador
    a = acoes(app)
    assert 'conta_excluida' in a and 'crianca_desativada' in a
    # login nao funciona mais
    r = post(client, '/entrar', email='mae@x.com', senha='senha12345')
    assert r.status_code == 200


def test_login_rate_limit_e_reset(client, app):
    cadastrar_e_entrar(client, app)
    client.get('/sair')
    for _ in range(5):
        post(client, '/entrar', email='mae@x.com', senha='errada123')
    r = post(client, '/entrar', email='mae@x.com', senha='senha12345')
    assert b'Muitas tentativas' in r.data
    from rede import seguranca
    seguranca.limpar_tentativas()
    post(client, '/esqueci-senha', email='mae@x.com')
    m = app.mailer.ultimo_para('mae@x.com')
    token = re.search(r'/resetar-senha/(\S+)', m['corpo']).group(1)
    r = post(client, f'/resetar-senha/{token}', senha='novasenha123', senha2='novasenha123')
    assert r.status_code == 302
    r = post(client, '/entrar', email='mae@x.com', senha='novasenha123')
    assert r.status_code == 302
    a = acoes(app)
    assert 'reset_solicitado' in a and 'senha_redefinida' in a and 'login_falhou' in a
