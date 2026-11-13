"""Nome falado da crianca (opcional, 13/11/2026): o que a voz diz e o que a familia ve antes do apelido."""

from datetime import datetime

import pytest
from sqlalchemy import text

from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post
from rede import voz
from rede.servicos import criancas as svc_cri, familia_telefones as fam
from rede.servicos.contas import ErroUsuario
from rede.tempo import TZ_SP


def test_validar_nome_e_exibicao():
    assert svc_cri.validar_nome(' Ana ') == 'Ana'
    assert svc_cri.validar_nome('Maria   Clara') == 'Maria Clara'
    assert svc_cri.validar_nome('Zé') == 'Zé' and svc_cri.validar_nome("D'Ávila") == "D'Ávila" and svc_cri.validar_nome('Ana-Lu') == 'Ana-Lu'
    assert svc_cri.validar_nome('') is None and svc_cri.validar_nome(None) is None and svc_cri.validar_nome('   ') is None
    for ruim in ('ana01', 'a' * 31, 'Ana!', '-Ana', 'Ana  -'):
        with pytest.raises(ErroUsuario):
            svc_cri.validar_nome(ruim)
    assert svc_cri.exibicao({'apelido': 'ana01', 'nome': 'Ana'}) == 'Ana (ana01)'
    assert svc_cri.exibicao({'apelido': 'ana01', 'nome': None}) == 'ana01'
    assert svc_cri.nome_falado({'apelido': 'ana01', 'nome': None}) == 'ana01'


def test_nome_no_cadastro_nas_telas_e_na_troca(client, app):
    cadastrar_e_entrar(client, app)
    r = post(client, '/crianca/nova', apelido='ana01', nome='Ana')
    assert r.status_code == 302
    cid = int(r.headers['Location'].rstrip('/').split('/')[-2])
    assert crianca_row(app, cid)['nome'] == 'Ana'
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'ID de Ana (ana01)' in html
    html = client.get('/criancas').get_data(as_text=True)
    assert 'Ana (ana01)' in html and 'Mudar o nome falado' in html
    # nome invalido no cadastro volta ao formulario
    r = post(client, '/crianca/nova', apelido='pedro02', nome='pedro02')
    assert r.status_code == 200 and 'sem números' in r.get_data(as_text=True)
    # pagina de nome: trocar e apagar
    assert 'value="Ana"' in client.get(f'/crianca/{cid}/nome').get_data(as_text=True)
    r = post(client, f'/crianca/{cid}/nome', nome='Aninha', follow_redirects=True)
    assert 'Nome de ana01: Aninha.' in r.get_data(as_text=True) and crianca_row(app, cid)['nome'] == 'Aninha'
    r = post(client, f'/crianca/{cid}/nome', nome='', follow_redirects=True)
    assert 'fica sem nome' in r.get_data(as_text=True) and crianca_row(app, cid)['nome'] is None
    assert 'Dar um nome falado' in client.get('/criancas').get_data(as_text=True)
    post(client, f'/crianca/{cid}/nome', nome='Ana')
    assert client.get('/meus-dados.json').get_json()['criancas'][0]['nome'] == 'Ana'
    # outra familia nao ve o nome: o cartao e os pedidos usam o apelido (o nome so entra nas telas da propria familia)
    assert 'Ana' not in client.get(f'/crianca/{cid}/cartao').get_data(as_text=True).replace('ana01', '')
    with app.engine.begin() as c:
        assert [r[0] for r in c.execute(text("SELECT acao FROM audit_log WHERE acao='crianca_nome_alterado'")).all()]


def test_menu_de_entrada_fala_o_nome_quando_nao_repete(client, app, monkeypatch):
    cadastrar_e_entrar(client, app)
    r = post(client, '/crianca/nova', apelido='ana01', nome='Ana'); cid_a = int(r.headers['Location'].rstrip('/').split('/')[-2])
    cr_a = crianca_row(app, cid_a)
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='outra@x.com', nome='Outra')
    r = post(client, '/crianca/nova', apelido='bia02', nome='Bia'); cid_b = int(r.headers['Location'].rstrip('/').split('/')[-2])
    cr_b = crianca_row(app, cid_b)
    from test_familia_telefones import _ativar_telefone
    _ativar_telefone(app, cid_a); _ativar_telefone(app, cid_b)
    com_audio = {cr_a['id_rede'], cr_b['id_rede']}
    monkeypatch.setattr(voz, 'tem_nome', lambda cfg, i: i in com_audio)
    t = TZ_SP.localize(datetime(2026, 11, 13, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr_a['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        fam.adicionar(c, cr_b['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'MENU' and [o['som'] for o in d['opcoes']] == [f"nomes/{cr_a['id_rede']}", f"nomes/{cr_b['id_rede']}"]
        # os dois com o mesmo nome: a voz volta ao apelido, que e unico
        svc_cri.definir_nome(c, cr_b, 'ana', app.cfg)
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert [o['som'] for o in d['opcoes']] == [f"apelidos/{cr_a['id_rede']}", f"apelidos/{cr_b['id_rede']}"]
        # sem audio do nome (voz desligada), apelido
        monkeypatch.setattr(voz, 'tem_nome', lambda cfg, i: False)
        svc_cri.definir_nome(c, cr_b, 'Bia', app.cfg)
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert [o['som'] for o in d['opcoes']] == [f"apelidos/{cr_a['id_rede']}", f"apelidos/{cr_b['id_rede']}"]
    assert voz.som_da_crianca(app.cfg, cr_a['id_rede']) is None   # testes sem voz: nenhum arquivo
