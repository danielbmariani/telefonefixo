"""Auditoria de seguranca (doc 14): senhas fracas, limite por conta, enumeracao de e-mail, cabecalhos, sessao."""

import re

from rede import seguranca
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def test_senhas_fracas():
    for s in ('12345678', 'senha123', 'aaaaaaaa', '87654321', 'qwerty123'):
        assert seguranca.senha_fraca(s), s
    assert seguranca.senha_fraca('mariani1', 'mariani@x.com')
    for s in ('gato-azul-7', 'MinhaCasa2026', 'tres tigres tristes'):
        assert not seguranca.senha_fraca(s, 'daniel@x.com'), s


def test_cadastro_recusa_senha_fraca_e_nao_enumera(client, app):
    r = post(client, '/cadastrar', email='n@x.com', senha='12345678', senha2='12345678', nome='n', follow_redirects=True)
    assert 'fácil de adivinhar'.encode() in r.data
    cadastrar_e_entrar(client, app, email='dona@x.com')
    client.get('/sair')
    r = post(client, '/cadastrar', email='dona@x.com', senha='Boa-senha-2026', senha2='Boa-senha-2026', nome='x', follow_redirects=True)
    # mesma tela e mesma mensagem de quem nao existe; dona recebe aviso por e-mail
    assert b'Enviamos um c' in r.data and 'já tiver conta'.encode() not in r.data
    assert 'tentou criar uma conta' in app.mailer.ultimo_para('dona@x.com')['assunto']
    r = post(client, '/verificar-email', codigo='000000', follow_redirects=True)
    assert 'Código incorreto ou expirado'.encode() in r.data and b'Nenhum cadastro' not in r.data


def test_login_limite_por_conta(client, app):
    cadastrar_e_entrar(client, app, email='alvo@x.com')
    client.get('/sair')
    seguranca.limpar_tentativas()
    # 15 tentativas erradas vindas de "IPs" diferentes (o limite por IP e 5; aqui o que conta e o por e-mail)
    for i in range(16):
        seguranca.limpar_tentativas() if i % 4 == 0 and False else None
        r = post(client, '/entrar', email='alvo@x.com', senha=f'errada{i}')
        if i % 4 == 3:
            # simula troca de IP zerando so o contador por IP
            seguranca._TENTATIVAS.pop('login:None', None)
            seguranca._TENTATIVAS.pop('login:127.0.0.1', None)
    r = post(client, '/entrar', email='alvo@x.com', senha='senha12345')
    assert b'Muitas tentativas' in r.data


def test_cabecalhos_e_sessao(client, app):
    r = client.get('/')
    assert r.headers['Content-Security-Policy'].startswith("default-src 'self'")
    assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
    assert r.headers['Permissions-Policy'].startswith('camera=()')
    assert r.headers['X-Frame-Options'] == 'DENY' and r.headers['X-Content-Type-Options'] == 'nosniff'
    assert app.config['PERMANENT_SESSION_LIFETIME'].total_seconds() == 12 * 3600
    cadastrar_e_entrar(client, app)
    with client.session_transaction() as s:
        assert s.permanent is True


def test_mensagem_de_pedido_escapada(client, app):
    a = client
    cadastrar_e_entrar(a, app, email='a@x.com'); ca = criar_crianca(a, 'anaa01'); ida = crianca_row(app, ca)['id_rede']
    b = app.test_client()
    cadastrar_e_entrar(b, app, email='b@x.com'); cb = criar_crianca(b, 'bebe02')
    r = post(b, f'/crianca/{cb}/contatos', acao='pedir', id_rede=ida, mensagem='<img src=x onerror=alert(1)>', follow_redirects=True)
    r = a.get(f'/crianca/{ca}/contatos')
    assert b'<img src=x' not in r.data and b'&lt;img src=x' in r.data
