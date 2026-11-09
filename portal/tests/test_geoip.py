"""Conferencia do fuso da familia pelo IP do telefone (rede/geoip.py): sem base nada acontece; com a base
(simulada), divergencia abre um caso 'fuso_divergente' uma vez e ele se resolve quando volta a bater."""

from datetime import datetime, timezone

from sqlalchemy import text, select

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, telefone_row, acoes, MAC, SN
from rede import db, geoip
from rede.servicos import contas


def test_divergente_compara_o_deslocamento_de_agora():
    ref = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    assert geoip.divergente('America/Sao_Paulo', 'America/Manaus', ref)
    assert not geoip.divergente('America/Cuiaba', 'America/Campo_Grande', ref)   # ambos UTC-4
    assert not geoip.divergente(None, 'America/Sao_Paulo', ref)                  # None = padrao
    assert not geoip.divergente('America/Sao_Paulo', None, ref)                  # sem fuso do IP: nada a comparar
    assert geoip.divergente('Europe/Lisbon', 'America/Sao_Paulo', ref)


def test_fuso_do_ip_sem_base_ou_ip_privado_devolve_none(app):
    assert not geoip.disponivel(app.cfg)                      # /var/lib/GeoIP nao existe nos testes
    assert geoip.fuso_do_ip('200.160.2.3', app.cfg) is None
    assert geoip.fuso_do_ip('192.168.0.10', app.cfg) is None
    assert geoip.fuso_do_ip('lixo', app.cfg) is None and geoip.fuso_do_ip(None, app.cfg) is None


def _preparar(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    t = telefone_row(app, cid)
    with app.engine.begin() as c:
        tok = c.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t AND ativo=1'), {'t': t['id']}).scalar()
    return cid, t, tok


def _casos(app, tipo='fuso_divergente'):
    with app.engine.begin() as c:
        return c.execute(select(db.casos).where(db.casos.c.tipo == tipo).order_by(db.casos.c.id)).mappings().all()


def test_provisionamento_sem_base_nao_abre_caso(client, app):
    cid, t, tok = _preparar(client, app)
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 200
    assert _casos(app) == [] and telefone_row(app, cid)['ultimo_prov_fuso'] is None


def test_ip_em_outro_fuso_abre_caso_uma_vez_e_resolve_quando_bate(client, app, monkeypatch):
    cid, t, tok = _preparar(client, app)
    monkeypatch.setattr(geoip, 'fuso_do_ip', lambda ip, cfg: 'America/Manaus')
    for _ in range(2):   # duas buscas: um caso so
        assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 200
    casos = _casos(app)
    assert len(casos) == 1 and casos[0]['estado'] == 'aberto' and casos[0]['gravidade'] == 'baixa'
    assert casos[0]['telefone_id'] == t['id'] and casos[0]['detalhes']['fuso_ip'] == 'America/Manaus'
    assert 'Amazonas' in casos[0]['descricao'] and 'Brasília' in casos[0]['descricao']
    assert telefone_row(app, cid)['ultimo_prov_fuso'] == 'America/Manaus'
    assert acoes(app, 'telefone', t['id']).count('alerta_fuso_divergente') == 1
    # o operador ve o caso e o fuso do IP na lista de telefones
    with app.engine.begin() as c:
        c.execute(text("UPDATE familias SET papel='operador' WHERE email='mae@x.com'"))
    assert 'fuso_divergente' in client.get('/ong/casos').data.decode()
    assert 'America/Manaus' in client.get('/ong/telefones').data.decode()
    # a familia corrige em /fuso para um fuso que bate com o IP: na busca seguinte o caso se resolve sozinho
    c = crianca_row(app, cid)
    with app.engine.begin() as conn:
        contas.definir_fuso(conn, c['familia_id'], 'America/Cuiaba')   # UTC-4, como Manaus
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 200
    casos = _casos(app)
    assert len(casos) == 1 and casos[0]['estado'] == 'resolvido' and casos[0]['resolvido_por'] == 'sistema'


def test_cadastro_sem_fuso_do_navegador_usa_o_ip(client, app, monkeypatch):
    import re
    monkeypatch.setattr(geoip, 'fuso_do_ip', lambda ip, cfg: 'America/Rio_Branco')
    post(client, '/cadastrar', email='ac@x.com', senha='senha12345', senha2='senha12345', nome='A')
    codigo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('ac@x.com')['corpo']).group(1)
    post(client, '/verificar-email', codigo=codigo)
    with app.engine.begin() as c:
        assert c.execute(text("SELECT fuso FROM familias WHERE email='ac@x.com'")).scalar() == 'America/Rio_Branco'
    # com o navegador mandando, o navegador ganha
    post(client, '/sair')
    client.get('/sair')
    post(client, '/cadastrar', email='pt@x.com', senha='senha12345', senha2='senha12345', nome='A', fuso='Europe/Lisbon')
    codigo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('pt@x.com')['corpo']).group(1)
    post(client, '/verificar-email', codigo=codigo)
    with app.engine.begin() as c:
        assert c.execute(text("SELECT fuso FROM familias WHERE email='pt@x.com'")).scalar() == 'Europe/Lisbon'
