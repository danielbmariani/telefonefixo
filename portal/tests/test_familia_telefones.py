"""Celulares da familia (B23): normalizacao, tela, 9+ID pelo tronco e entrada pelo tronco."""

from datetime import datetime

import pytest

from rede.servicos import familia_telefones as fam, chamadas, criancas as svc_cri, historico
from rede.servicos.contas import ErroUsuario
from rede.tempo import TZ_SP
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def test_normalizar_e_formatar():
    assert fam.normalizar('+55 (11) 98765-4321') == '11987654321'
    assert fam.normalizar('011987654321') == '11987654321'
    assert fam.normalizar('+5511987654321') == '11987654321'
    assert fam.normalizar('11 5108 3530') == '1151083530'
    assert fam.formatar('11987654321') == '(11) 98765-4321'
    assert fam.formatar('1151083530') == '(11) 5108-3530'
    for ruim in ('987654321', '10987654321', '11887654321', '', 'abc'):
        with pytest.raises(ErroUsuario):
            fam.normalizar(ruim)


def _ativar_telefone(app, crianca_id):
    from sqlalchemy import insert
    from rede import db
    from rede.tempo import agora
    with app.engine.begin() as c:
        c.execute(insert(db.telefones).values(crianca_id=crianca_id, mac='C074AD010203', serial='SN1', modelo='grp',
                                              estado='ativo', admin_senha='x', informado_em=agora()))


def test_tela_cadastra_e_remove(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    r = client.get('/celulares')
    assert r.status_code == 200 and 'Nenhum celular cadastrado'.encode() in r.data
    r = post(client, '/celulares', numero='(11) 98765-4321', apelido='  Mãe  ', follow_redirects=True)
    assert '(11) 98765-4321'.encode() in r.data and 'Mãe'.encode() in r.data
    # repetido e limite
    r = post(client, '/celulares', numero='11987654321', apelido='x', follow_redirects=True)
    assert 'já está cadastrado'.encode() in r.data
    post(client, '/celulares', numero='11911111111', apelido='Pai')
    r = post(client, '/celulares', numero='11933333333', apelido='Tio', follow_redirects=True)
    assert 'No máximo 2'.encode() in r.data
    fid = crianca_row(app, cid)['familia_id']
    with app.engine.begin() as c:
        rows = fam.listar(c, fid)
        assert [(t['numero'], t['posicao']) for t in rows] == [('11987654321', 1), ('11911111111', 2)]
        primeiro = rows[0]['id']
    # trocar ordem pela tela
    r = post(client, '/celulares', acao='trocar', follow_redirects=True)
    assert 'Ordem trocada'.encode() in r.data
    with app.engine.begin() as c:
        assert [(t['numero'], t['posicao']) for t in fam.listar(c, fid)] == [('11911111111', 1), ('11987654321', 2)]
    # cartao mostra 9 e 8 com os apelidos
    r = client.get(f'/crianca/{cid}/cartao')
    cr = crianca_row(app, cid)
    assert f"Pai (celular)".encode() in r.data and f"9{cr['id_rede']}#".encode() in r.data and f"8{cr['id_rede']}#".encode() in r.data
    r = post(client, '/celulares', acao='remover', id=str(primeiro), follow_redirects=True)
    assert 'Número removido'.encode() in r.data
    with app.engine.begin() as c:
        rows = fam.listar(c, fid)
        assert len(rows) == 1 and rows[0]['posicao'] == 1          # ficou so o Pai, na posicao 1
        # readicionar reativa a mesma linha, na posicao livre (2)
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        rows = fam.listar(c, fid)
        assert [(t['apelido'], t['posicao']) for t in rows] == [('Pai', 1), ('Mãe', 2)]


def test_nove_mais_id_decide(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    outra = crianca_row(app, criar_crianca(client, 'bia02'))
    t = TZ_SP.localize(datetime(2026, 10, 27, 15, 0))
    with app.engine.begin() as c:
        # sem celular cadastrado
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], t) == ('BLOCK_PARENT', 'FAMILIA_NAO_CONFIGURADA')
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        # so o celular 1: 9 funciona, 8 ainda nao
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], t) == ('ALLOW', 'PJSIP/11987654321@nvoip;limite=1000')
        assert chamadas.decidir(c, cr['id_rede'], '8' + cr['id_rede'], t) == ('BLOCK_PARENT', 'FAMILIA_NAO_CONFIGURADA')
        fam.adicionar(c, cr['familia_id'], '11911111111', 'Pai')
        assert chamadas.decidir(c, cr['id_rede'], '8' + cr['id_rede'], t) == ('ALLOW', 'PJSIP/11911111111@nvoip;limite=1000')
        # 9 + ID de outra crianca (mesmo da mesma familia) nao vale
        assert chamadas.decidir(c, cr['id_rede'], '9' + outra['id_rede'], t)[0] == 'BLOCK_PERMISSION'
        # crianca desconhecida
        assert chamadas.decidir(c, '299999', '9299999', t)[0] == 'BLOCK_UNKNOWN'
        # rotulos no historico
        n = historico.nomes(c, ['9' + cr['id_rede'], '11987654321', cr['id_rede']])
        assert n['9' + cr['id_rede']] == 'Celular 1 da família'
        assert historico.nomes(c, ['8' + cr['id_rede']])['8' + cr['id_rede']] == 'Celular 2 da família'
        assert n['11987654321'] == 'Celular da família (11) 98765-4321'
        assert n[cr['id_rede']] == 'ana01'


def test_nove_mais_id_respeita_horario(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    post(client, f'/crianca/{cid}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_11 = TZ_SP.localize(datetime(2026, 10, 26, 11, 0))
    seg_15 = TZ_SP.localize(datetime(2026, 10, 26, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], seg_11)[0] == 'ALLOW'
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], seg_15)[0] == 'BLOCK_SCHEDULE_CALLER'


def test_entrada_pelo_tronco(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    cid2 = criar_crianca(client, 'bia02')
    cr2 = crianca_row(app, cid2)
    t = TZ_SP.localize(datetime(2026, 10, 27, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        # numero desconhecido
        assert fam.decidir_entrada(c, '11900000000', t)[0] == 'BLOCK_UNKNOWN'
        assert fam.decidir_entrada(c, 'anonymous', t)[0] == 'BLOCK_UNKNOWN'
        # numero do chamador no display name (Nvoip) ou no P-Asserted-Identity; From user = nosso tronco
        assert fam.numero_do_identificador('15XXXXXXX', '11987654321') == '11987654321'
        assert fam.numero_do_identificador('15XXXXXXX', '', '"x" <sip:+5511987654321@op.br>;party=calling') == '11987654321'
        assert fam.numero_do_identificador('15XXXXXXX', 'Anonymous', '') == ''
        # conhecido, mas nenhuma crianca com telefone conectado
        assert fam.decidir_entrada(c, '+5511987654321', t)[0] == 'BLOCK_NO_PHONE'
        assert fam.decidir_entrada(c, '15XXXXXXX', t, '11987654321')[0] == 'BLOCK_NO_PHONE'
    _ativar_telefone(app, cid)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '+5511987654321', t)
        assert res == 'ALLOW' and d['ids'] == [cr['id_rede']] and d['dial'] == f"PJSIP/{cr['id_rede']}" and d['nome'] == 'Mãe'
        assert d['numero'] == '11987654321'
        # identificador sem o nono digito tambem casa
        assert fam.decidir_entrada(c, '1187654321', t)[0] == 'ALLOW'
    _ativar_telefone(app, cid2)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '11987654321', t)
        assert res == 'ALLOW' and sorted(d['ids']) == sorted([cr['id_rede'], cr2['id_rede']])
        assert '&' in d['dial']
    # fora do horario de todas -> BLOCK_SCHEDULE_DEST
    post(client, f'/crianca/{cid}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    post(client, f'/crianca/{cid2}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_15 = TZ_SP.localize(datetime(2026, 10, 26, 15, 0))
    with app.engine.begin() as c:
        assert fam.decidir_entrada(c, '11987654321', seg_15)[0] == 'BLOCK_SCHEDULE_DEST'
    # removido -> desconhecido
    with app.engine.begin() as c:
        tid = fam.listar(c, cr['familia_id'])[0]['id']
        fam.remover(c, cr['familia_id'], tid)
        assert fam.decidir_entrada(c, '11987654321', t)[0] == 'BLOCK_UNKNOWN'
