"""Formulario de contato: vira caso no painel e e-mail de aviso."""

from sqlalchemy import text

from conftest import post, cadastrar_e_entrar
from rede import seguranca
from rede.servicos import contas


def _operador(client, app):
    with app.engine.begin() as c:
        contas.criar_operador(c, 'op@ong.org', 'senha12345', 'Op')
    client.get('/sair')
    post(client, '/entrar', email='op@ong.org', senha='senha12345')


def test_mensagem_vira_caso_e_email(client, app):
    seguranca.limpar_tentativas()
    assert 'Escreva para nós' in client.get('/contato').get_data(as_text=True)
    r = post(client, '/contato', nome='Rita', email='rita@x.com', mensagem='O telefone da minha filha não ouve o celular desde ontem.')
    assert r.status_code == 302
    with app.engine.begin() as c:
        caso = c.execute(text("SELECT tipo, gravidade, estado, familia_id, descricao FROM casos")).mappings().first()
    assert caso['tipo'] == 'mensagem' and caso['estado'] == 'aberto' and caso['familia_id'] is None
    assert 'Rita <rita@x.com>' in caso['descricao']
    m = app.mailer.ultimo_para(app.cfg.ALERTA_EMAIL)
    assert 'Mensagem pelo site de Rita' in m['assunto'] and 'rita@x.com' in m['corpo'] and 'não ouve o celular' in m['corpo'] and '/ong/casos' in m['corpo']
    # curta demais e robo (campo escondido) nao criam caso
    post(client, '/contato', nome='Rita', email='rita@x.com', mensagem='oi')
    post(client, '/contato', nome='Bot', email='bot@x.com', mensagem='compre agora mesmo este produto', site='http://spam')
    with app.engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM casos")).scalar() == 1
    # painel mostra a mensagem inteira
    _operador(client, app)
    html = client.get('/ong/casos').get_data(as_text=True)
    assert 'não ouve o celular desde ontem' in html and 'rita@x.com' in html


def test_mensagem_de_familia_logada_fica_ligada_a_conta_e_tem_limite(client, app):
    seguranca.limpar_tentativas()
    cadastrar_e_entrar(client, app)
    html = client.get('/contato').get_data(as_text=True)
    assert 'value="mae@x.com"' in html
    for i in range(5):
        post(client, '/contato', nome='Mãe', email='mae@x.com', mensagem=f'Mensagem de teste número {i} com texto suficiente.')
    r = post(client, '/contato', nome='Mãe', email='mae@x.com', mensagem='A sexta mensagem na mesma hora deve ser recusada.', follow_redirects=True)
    assert 'Muitas mensagens seguidas' in r.get_data(as_text=True)
    with app.engine.begin() as c:
        rows = c.execute(text("SELECT familia_id FROM casos WHERE tipo = 'mensagem'")).all()
    assert len(rows) == 5 and all(r[0] for r in rows)
