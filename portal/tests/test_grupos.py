"""Grupos para ligar juntos (doc 16): criacao, codigos por crianca, regra do clique, decisao da chamada,
registro no historico."""
from datetime import datetime

import pytest
from sqlalchemy import text

from rede.servicos import grupos, criancas as svc_cri, amizades as svc_ami, horarios as svc_hor
from rede.servicos.contas import ErroUsuario
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def _familia(client, app, email, apelidos):
    cadastrar_e_entrar(client, app, email=email)
    out = []
    for a in apelidos:
        cid = criar_crianca(client, a)
        out.append(crianca_row(app, cid))
    client.get('/sair')
    return out


def _amigos(app, a, b):
    """Amizade aceita entre as criancas a e b (linhas), direto no banco."""
    with app.engine.begin() as conn:
        fam_a = conn.execute(text('SELECT familia_id FROM criancas WHERE id=:i'), {'i': a['id']}).scalar()
        fam_b = conn.execute(text('SELECT familia_id FROM criancas WHERE id=:i'), {'i': b['id']}).scalar()
        from rede.config import Config
        am = svc_ami.pedir(conn, a, b['id_rede'], fam_a, Config(env={}, AMBIENTE='teste', MAIL_BACKEND='memoria',
                                                                  SECRET_KEY='x' * 64), sem_limites=True)
        svc_ami.responder(conn, am['id'], fam_b, 'aceitar')


@pytest.fixture
def rede4(client, app):
    """Quatro criancas em quatro familias: jose e amigo de beto, alice e theo; beto e amigo de alice; theo so de jose."""
    jose, = _familia(client, app, 'j@x.com', ['jose'])
    beto, = _familia(client, app, 'b@x.com', ['beto'])
    alice, = _familia(client, app, 'a@x.com', ['alice'])
    theo, = _familia(client, app, 't@x.com', ['theo'])
    for a, b in ((jose, beto), (jose, alice), (jose, theo), (beto, alice)):
        _amigos(app, a, b)
    return {'jose': jose, 'beto': beto, 'alice': alice, 'theo': theo}


def _fam_id(app, c):
    with app.engine.begin() as conn:
        return conn.execute(text('SELECT familia_id FROM criancas WHERE id=:i'), {'i': c['id']}).scalar()


def test_criar_lista_codigos_e_cartao(app, rede4):
    j, b, a, t = rede4['jose'], rede4['beto'], rede4['alice'], rede4['theo']
    with app.engine.begin() as conn:
        g = grupos.criar(conn, _fam_id(app, j), j, '  Turma do   futebol ', [b['id'], a['id'], t['id']])
        assert g['nome'] == 'Turma do futebol'
        meus = grupos.listar_da_crianca(conn, j)
        assert len(meus) == 1 and meus[0]['discar'] == '01' and meus[0]['dona'] and meus[0]['faltam'] == []
        assert [m['apelido'] for m in meus[0]['membros']] == ['jose', 'beto', 'alice', 'theo']
        # na casa do theo: ele nao e amigo de beto nem de alice; o site diz isso so para a familia dele
        do_theo = grupos.listar_da_crianca(conn, t)
        assert do_theo[0]['discar'] == '01' and sorted(do_theo[0]['faltam']) == ['alice', 'beto'] and not do_theo[0]['dona']
        # segundo grupo do jose ganha codigo 2; para o beto e o primeiro, codigo 1
        g2 = grupos.criar(conn, _fam_id(app, j), j, 'Vizinhos', [b['id']])
        assert [x['discar'] for x in grupos.listar_da_crianca(conn, j)] == ['01', '02']
        assert [x['discar'] for x in grupos.listar_da_crianca(conn, b)] == ['01', '02']
        assert grupos.para_cartao(conn, j) == [('Turma do futebol', '01'), ('Vizinhos', '02')]
        # so amigos aceitos; nome curto; pelo menos um amigo
        with pytest.raises(ErroUsuario):
            grupos.criar(conn, _fam_id(app, b), b, 'X', [t['id']])   # theo nao e amigo do beto
        with pytest.raises(ErroUsuario):
            grupos.criar(conn, _fam_id(app, j), j, 'Nome comprido demais para o visor', [b['id']])
        with pytest.raises(ErroUsuario):
            grupos.criar(conn, _fam_id(app, j), j, 'Vazio', [])
        assert g2['ativo']


def test_sair_e_remover(app, rede4):
    j, b, a = rede4['jose'], rede4['beto'], rede4['alice']
    with app.engine.begin() as conn:
        g = grupos.criar(conn, _fam_id(app, j), j, 'Trio', [b['id'], a['id']])
        grupos.sair(conn, _fam_id(app, a), g['id'], a)
        assert [m['apelido'] for m in grupos.listar_da_crianca(conn, j)[0]['membros']] == ['jose', 'beto']
        assert grupos.listar_da_crianca(conn, a) == []
        with pytest.raises(ErroUsuario):
            grupos.remover(conn, _fam_id(app, b), g['id'], b)   # so a dona remove
        grupos.sair(conn, _fam_id(app, b), g['id'], b)        # sobrou um: grupo encerra
        assert grupos.por_id(conn, g['id'])['ativo'] is False
        assert grupos.listar_da_crianca(conn, j) == []
        # o codigo 1 do jose ficou livre de novo
        g3 = grupos.criar(conn, _fam_id(app, j), j, 'Outro', [b['id']])
        assert grupos.listar_da_crianca(conn, j)[0]['discar'] == '01'
        grupos.remover(conn, _fam_id(app, j), g3['id'], j)
        assert grupos.listar_da_crianca(conn, b) == []


def test_decidir_clique_horario_e_bloqueios(app, rede4):
    j, b, a, t = rede4['jose'], rede4['beto'], rede4['alice'], rede4['theo']
    agora = datetime(2026, 10, 28, 15, 0)
    with app.engine.begin() as conn:
        g = grupos.criar(conn, _fam_id(app, j), j, 'Turma', [b['id'], a['id'], t['id']])
        d = grupos.decidir(conn, j['id_rede'], '1', agora)
        assert d['resultado'] == 'ALLOW' and d['grupo']['nome'] == 'Turma' and d['caller']['apelido'] == 'jose'
        # beto e alice sao amigos entre si e do jose: entram; theo nao e amigo de beto: fica fora por amizade
        assert [c['apelido'] for c in d['chamar']] == ['beto', 'alice']
        assert d['fora'] == [{'id_rede': t['id_rede'], 'apelido': 'theo', 'motivo': 'amizade'}]
        # theo ligando: so o jose e amigo dele; beto e alice ficam fora
        d2 = grupos.decidir(conn, t['id_rede'], '1', agora)
        assert [c['apelido'] for c in d2['chamar']] == ['jose'] and sorted(x['apelido'] for x in d2['fora']) == ['alice', 'beto']
        # alice silenciada: fica fora por horario
        svc_hor.silenciar(conn, a['id'], '1h', _fam_id(app, a))
        d3 = grupos.decidir(conn, j['id_rede'], '1', agora)
        assert [c['apelido'] for c in d3['chamar']] == ['beto'] and {x['apelido']: x['motivo'] for x in d3['fora']} == {'alice': 'horario', 'theo': 'amizade'}
        # codigo que nao existe; crianca fora do proprio horario
        assert grupos.decidir(conn, j['id_rede'], '7', agora)['resultado'] == 'BLOCK_UNKNOWN'
        svc_hor.silenciar(conn, j['id'], '1h', _fam_id(app, j))
        assert grupos.decidir(conn, j['id_rede'], '1', agora)['resultado'] == 'BLOCK_SCHEDULE_CALLER'
        assert grupos.pode_entrar(conn, t['id_rede'], [j['id_rede']]) and not grupos.pode_entrar(conn, t['id_rede'], [j['id_rede'], b['id_rede']])
        assert g['ativo']


def test_registrar_chamada_no_historico(app, rede4):
    j, b = rede4['jose'], rede4['beto']
    with app.engine.begin() as conn:
        grupos.registrar_chamada(conn, {j['id_rede']: [(1000, 1100)], b['id_rede']: [(1020, 1080)]}, '2026-10-28 15:00:00')
        rows = conn.execute(text("SELECT caller_ext, callee_ext, status, duration_seconds, block_reason FROM call_logs ORDER BY caller_ext")).all()
    assert len(rows) == 2 and all(r[1] == 'GRUPO' and r[2] == 'ALLOWED' for r in rows)
    por = {r[0]: r for r in rows}
    assert por[j['id_rede']][3] == 100 and por[j['id_rede']][4] == f'{b["id_rede"]}:60'
    assert por[b['id_rede']][3] == 60 and por[b['id_rede']][4] == f'{j["id_rede"]}:60'


def test_apelido_falado():
    from rede import voz
    assert voz.texto_do_apelido('jose07') == 'jose 0 7'
    assert voz.texto_do_apelido('maria_clara') == 'maria clara'


def test_site_cria_lista_sai_e_cartao(client, app, rede4):
    """Pela aba Amigos: a familia do jose cria o grupo; o cartao mostra a linha; a familia do beto ve e sai."""
    j, b, a = rede4['jose'], rede4['beto'], rede4['alice']
    from conftest import post as _post
    # entra como a familia do jose
    _post(client, '/entrar', email='j@x.com', senha='senha12345')
    r = client.get(f'/crianca/{j["id"]}/contatos').get_data(as_text=True)
    assert 'Grupos para ligar juntos' in r and 'Criar um grupo' in r and f'value="{b["id"]}"' in r
    r = _post(client, f'/crianca/{j["id"]}/contatos', acao='grupo_criar', nome='Turma do futebol', membros=[str(b['id']), str(a['id'])], follow_redirects=True)
    h = r.get_data(as_text=True)
    assert 'criado. No telefone de jose, disca 01#' in h and 'Remover grupo' in h
    cart = client.get(f'/crianca/{j["id"]}/cartao').get_data(as_text=True)
    assert 'Turma do futebol (grupo)' in cart and '01#' in cart and 'disque <strong>0</strong>' not in cart
    # erro de validacao vira mensagem, nao 500
    r = _post(client, f'/crianca/{j["id"]}/contatos', acao='grupo_criar', nome='X', membros=[str(b['id'])], follow_redirects=True)
    assert 'nome do grupo deve ter' in r.get_data(as_text=True)
    client.get('/sair')
    # a familia do beto ve o grupo criado pela familia do jose e sai
    _post(client, '/entrar', email='b@x.com', senha='senha12345')
    h = client.get(f'/crianca/{b["id"]}/contatos').get_data(as_text=True)
    assert 'Turma do futebol' in h and 'criado pela família de jose' in h and 'Sair do grupo' in h and 'Remover grupo' not in h
    with app.engine.begin() as conn:
        gid = grupos.listar_da_crianca(conn, b)[0]['id']
    r = _post(client, f'/crianca/{b["id"]}/contatos', acao='grupo_sair', grupo_id=gid, follow_redirects=True)
    assert 'saiu do grupo' in r.get_data(as_text=True)
    with app.engine.begin() as conn:
        assert [m['apelido'] for m in grupos.listar_da_crianca(conn, j)[0]['membros']] == ['jose', 'alice']
