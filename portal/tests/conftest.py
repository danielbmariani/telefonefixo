import os
import re

import pytest
from sqlalchemy import text

from rede import create_app, db, seguranca
from rede.config import Config


@pytest.fixture
def app(tmp_path):
    cfg = Config(env={}, AMBIENTE='teste', DATABASE_URL=f'sqlite:///{tmp_path}/t.db', MAIL_BACKEND='memoria',
                 GDMS_MODO='simulado', SITE_URL='http://teste', PROV_URL='https://prov.teste', SIP_HOST='sip.teste',
                 SECRET_KEY='x' * 64)
    a = create_app(cfg)
    a.config['TESTING'] = True
    db.init_db(a.engine, com_ps_contacts=True)
    seguranca.limpar_tentativas()
    yield a
    a.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client):
    """Obtem token CSRF carregando uma pagina GET."""
    client.get('/entrar')
    with client.session_transaction() as s:
        return s['_csrf_token']


def post(client, url, follow_redirects=False, **dados):
    dados['_csrf_token'] = csrf(client)
    return client.post(url, data=dados, follow_redirects=follow_redirects)


def cadastrar_e_entrar(client, app, email='mae@x.com', senha='senha12345', nome='Mae'):
    post(client, '/cadastrar', email=email, senha=senha, senha2=senha, nome=nome)
    m = app.mailer.ultimo_para(email)
    codigo = re.search(r'\b(\d{6})\b', m['corpo']).group(1)
    r = post(client, '/verificar-email', codigo=codigo)
    assert r.status_code == 302
    # consentimento
    r = post(client, '/consentimento', aceito_termos='sim', aceito_privacidade='sim', aceito_crianca='sim')
    assert r.status_code == 302
    return email


def criar_crianca(client, apelido='jose07'):
    r = post(client, '/crianca/nova', apelido=apelido)
    assert r.status_code == 302, r.data
    return int(r.headers['Location'].rstrip('/').split('/')[-2])


def crianca_row(app, crianca_id):
    from rede.servicos import criancas
    with app.engine.begin() as c:
        return criancas.por_id(c, crianca_id)


def telefone_row(app, crianca_id):
    from rede.servicos import telefones
    with app.engine.begin() as c:
        return telefones.atual_da_crianca(c, crianca_id)


def acoes(app, objeto_tipo=None, objeto_id=None):
    with app.engine.begin() as c:
        q = 'SELECT acao FROM audit_log'
        params = {}
        if objeto_tipo:
            q += ' WHERE objeto_tipo=:t AND objeto_id=:i'
            params = {'t': objeto_tipo, 'i': str(objeto_id)}
        return [r[0] for r in c.execute(text(q + ' ORDER BY id'), params).all()]


MAC = 'C0:74:AD:01:02:03'
SN = 'SN12345678AB'
