"""Aba Telefones, Adicionar telefone, DDD da casa e cartao (doc 20, etapa C)."""

import re

from sqlalchemy import text

from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post
from rede import geoip
from rede.servicos import familia_telefones as fam


def _fid(app, cid):
    return crianca_row(app, cid)['familia_id']


def test_adicionar_telefone_sem_ddd_usa_e_grava_o_ddd_da_casa(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    # sem pista nenhuma: a pagina pede DDD e nao inventa
    html = client.get(f'/crianca/{cid}/telefones/novo').get_data(as_text=True)
    assert 'Com DDD.' in html and 'Escolha o DDD da casa' in html
    r = post(client, f'/crianca/{cid}/telefones/novo', apelido='Vó Lúcia', numero='3456 7890', recebe='1', follow_redirects=True)
    assert 'Digite o número com DDD' in r.get_data(as_text=True)
    # com celular de casa, o DDD dele vira a sugestao
    post(client, f'/crianca/{cid}/telefones/novo-celular', numero='11987654321', apelido='Mãe')
    html = client.get(f'/crianca/{cid}/telefones/novo').get_data(as_text=True)
    assert 'vale o <strong>11</strong>, DDD da casa (pelos celulares de casa)' in html
    r = post(client, f'/crianca/{cid}/telefones/novo', apelido='Vó Lúcia', numero='3456 7890', recebe='1', follow_redirects=True)
    html = r.get_data(as_text=True)
    assert 'Vó Lúcia: (11) 3456-7890. ana01 disca 3456 7890#. DDD da casa: 11.' in html
    with app.engine.begin() as c:
        fam_row = c.execute(text('SELECT ddd, ddd_origem FROM familias WHERE id=:f'), {'f': _fid(app, cid)}).first()
        assert tuple(fam_row) == ('11', 'celulares')
        outros = fam.listar_outros(c, _fid(app, cid))
        assert [(t['apelido'], t['numero'], t['recebe']) for t in outros] == [('Vó Lúcia', '1134567890', True)]
    # com DDD de fora e sem a caixa marcada: nao recebe; a lista mostra o DDD no "discar"
    r = post(client, f'/crianca/{cid}/telefones/novo', apelido='Padaria', numero='(19) 3333-4444', follow_redirects=True)
    html = r.get_data(as_text=True)
    assert 'Padaria: (19) 3333-4444. ana01 disca 19 3333 4444#.' in html and 'DDD da casa' in html
    assert 'só ana01 liga' in html and 'liga para ana01' in html
    assert 'DDD da casa: <strong class="mono">11</strong> (São Paulo e região)' in html
    # erro volta ao formulario com o que foi digitado
    r = post(client, f'/crianca/{cid}/telefones/novo', apelido='Banco', numero='0800 123 4567')
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'número de serviço' in html and 'value="0800 123 4567"' in html and 'value="Banco"' in html
    r = post(client, f'/crianca/{cid}/telefones/novo', apelido='  ', numero='11 2222 3333')
    assert 'Diga quem é' in r.get_data(as_text=True)
    # mudar recebe e remover pela lista
    with app.engine.begin() as c:
        padaria = next(t for t in fam.listar_outros(c, _fid(app, cid)) if t['apelido'] == 'Padaria')
    r = post(client, f'/crianca/{cid}/telefones', acao='recebe', id=str(padaria['id']), valor='1', follow_redirects=True)
    assert 'Padaria agora pode ligar para ana01' in r.get_data(as_text=True)
    r = post(client, f'/crianca/{cid}/telefones', acao='remover', id=str(padaria['id']), follow_redirects=True)
    assert 'Número removido' in r.get_data(as_text=True) and 'Padaria' not in r.get_data(as_text=True)
    # cartao: outros com o que discar, dica do DDD
    html = client.get(f'/crianca/{cid}/cartao').get_data(as_text=True)
    assert '<td>Vó Lúcia</td><td class="ext">3456 7890#</td>' in html and 'disque o DDD antes, sem o 0' in html


def test_pagina_ddd_sugere_pelo_telefone_e_salva_a_escolha(client, app, monkeypatch):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    fid = _fid(app, cid)
    monkeypatch.setattr(geoip, 'registro', lambda ip, cfg: {'pais': 'BR', 'cidade': 'Campinas', 'uf': 'SP', 'raio_km': 10, 'lat': -22.9, 'lon': -47.06} if ip == '7.7.7.7' else None)
    from sqlalchemy import insert
    from rede import db
    from rede.tempo import agora
    with app.engine.begin() as c:
        c.execute(insert(db.telefones).values(crianca_id=cid, mac='C074AD010203', serial='SN1', modelo='grp', estado='ativo',
                                              admin_senha='x', informado_em=agora(), ultimo_prov_em=agora(), ultimo_prov_ip='7.7.7.7'))
    html = client.get(f'/ddd?crianca_id={cid}').get_data(as_text=True)
    assert 'Sugestão: <strong class="mono">19</strong> (Campinas e região), pelo telefone de ana01, a casa parece estar em Campinas, SP.' in html
    assert '<option value="19" selected>' in html
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'DDD da casa: <strong class="mono">19</strong> (Campinas e região)<span class="text-muted">, sugerido pelo telefone de ana01' in html
    assert 'Confirmar ou trocar o DDD' in html
    r = post(client, f'/ddd?crianca_id={cid}', ddd='11')
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/crianca/{cid}/telefones')
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'DDD da casa: <strong class="mono">11</strong> (São Paulo e região).' in html and 'Trocar o DDD' in html
    with app.engine.begin() as c:
        assert tuple(c.execute(text('SELECT ddd, ddd_origem FROM familias WHERE id=:f'), {'f': fid}).first()) == ('11', 'familia')
    r = post(client, f'/ddd?crianca_id={cid}', ddd='10', follow_redirects=True)
    assert 'Escolha um DDD da lista' in r.get_data(as_text=True)
    # voltar=novo leva de volta ao formulario
    r = post(client, f'/ddd?crianca_id={cid}&voltar=novo', ddd='19')
    assert r.headers['Location'].endswith(f'/crianca/{cid}/telefones/novo')


def test_recurso_desligado_esconde_o_bloco(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    app.cfg.MAX_OUTROS = 0
    try:
        html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
        assert 'Outros telefones' not in html and 'Como ana01 disca' not in html and 'Celulares de casa' in html
        assert client.get(f'/crianca/{cid}/telefones/novo').status_code == 404
    finally:
        app.cfg.MAX_OUTROS = 20
