"""LGPD / ECA Digital (doc 13): exportacao, contato, retencao e exclusao completa."""

import json
from datetime import timedelta

from sqlalchemy import text, insert

from rede import db
from rede.servicos import retencao, familia_telefones as fam
from rede.tempo import agora, em_sp
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post, acoes, MAC, SN


def test_contato_publico_e_rodape(client, app):
    r = client.get('/contato')
    assert r.status_code == 200
    assert b'contato@telefonefixo.org' in r.data and b'privacidade@telefonefixo.org' in r.data and b'Disque 100' in r.data
    r = client.get('/')
    assert 'Contato e denúncias'.encode() in r.data and 'a partir de 6 anos'.encode() in r.data
    for u in ('/termos', '/privacidade'):
        r = client.get(u)
        assert r.status_code == 200 and b'2026-10-' in r.data
    # textos: sem travessao e com os canais
    import pathlib
    for f in pathlib.Path('rede/textos').glob('*.md'):
        t = f.read_text(encoding='utf-8')
        assert '—' not in t and '–' not in t, f
    assert 'privacidade@telefonefixo.org' in pathlib.Path('rede/textos/privacidade.md').read_text(encoding='utf-8')


def _ligacao(app, de, para, ts, status='ALLOWED', dur=10):
    with app.engine.begin() as c:
        c.execute(insert(db.call_logs).values(caller_ext=de, callee_ext=para, timestamp=ts, status=status, duration_seconds=dur))


def test_meus_dados_exporta_tudo(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    post(client, '/celulares', numero='11987654321', apelido='Mãe')
    _ligacao(app, cr['id_rede'], '9' + cr['id_rede'], '2026-10-27 10:00:00')
    r = client.get('/meus-dados.json')
    assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
    d = json.loads(r.data)
    assert d['responsavel']['email'] == 'mae@x.com'
    assert {c['tipo'] for c in d['consentimentos']} == {'termos', 'privacidade', 'crianca'}
    assert d['celulares'][0]['numero'] == '11987654321'
    cri = d['criancas'][0]
    assert cri['apelido'] == 'ana01' and cri['id'] == cr['id_rede']
    assert cri['telefones'][0]['mac'] == 'C074AD010203'
    assert cri['ligacoes'][0]['callee_ext'] == '9' + cr['id_rede']
    assert 'dados_exportados' in acoes(app)


def test_retencao_agrega_e_apaga(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    velho = em_sp(agora() - timedelta(days=100)).strftime('%Y-%m-%d 09:00:00')
    velho2 = em_sp(agora() - timedelta(days=100)).strftime('%Y-%m-%d 10:00:00')
    novo = em_sp(agora() - timedelta(days=5)).strftime('%Y-%m-%d 09:00:00')
    _ligacao(app, cr['id_rede'], '234567', velho, dur=30)
    _ligacao(app, cr['id_rede'], '234567', velho2, status='BLOCKED', dur=None)
    _ligacao(app, cr['id_rede'], '234567', novo, dur=12)
    with app.engine.begin() as c:
        r = retencao.aplicar(c, app.cfg)
        assert r == {'chamadas_apagadas': 2, 'dias': 1}
        assert c.execute(text('SELECT count(*) FROM call_logs')).scalar() == 1
        dia, n, segs, bloq = c.execute(text('SELECT dia, chamadas, segundos, bloqueadas FROM chamadas_resumo')).first()
        assert dia == velho[:10] and n == 2 and segs == 30 and bloq == 1
        # rodar de novo nao muda nada
        assert retencao.aplicar(c, app.cfg)['chamadas_apagadas'] == 0
    assert 'retencao_chamadas_aplicada' in acoes(app)


def test_exclusao_apaga_celulares_e_ligacoes(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    post(client, '/celulares', numero='11987654321', apelido='Mãe')
    _ligacao(app, cr['id_rede'], '9' + cr['id_rede'], '2026-10-27 10:00:00')
    _ligacao(app, '11987654321', cr['id_rede'], '2026-10-27 11:00:00')
    r = post(client, '/excluir-conta', confirmacao='EXCLUIR')
    assert r.status_code == 302
    with app.engine.begin() as c:
        assert c.execute(text('SELECT count(*) FROM familia_telefones')).scalar() == 0
        assert c.execute(text('SELECT count(*) FROM call_logs')).scalar() == 0
        apelido = c.execute(text('SELECT apelido FROM criancas')).scalar()
        assert apelido.startswith('removido-')
        # consentimentos ficam como prova
        assert c.execute(text('SELECT count(*) FROM consentimentos')).scalar() == 3


def test_previa_de_compartilhamento(client, app):
    r = client.get('/')
    h = r.data.decode()
    assert 'property="og:image" content="http://teste/static/og.png"' in h
    assert 'property="og:title" content="Telefone Fixo: adiar o celular sem isolar as crianças"' in h
    assert 'name="twitter:card" content="summary_large_image"' in h
    assert client.get('/static/og.png').status_code == 200
