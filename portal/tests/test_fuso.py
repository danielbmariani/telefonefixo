"""Fuso horario da casa: cadastro, pagina /fuso, relogio do telefone, horarios e datas no fuso da familia."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, acoes
from rede import db, fusos
from rede.servicos import horarios, telefones as svc_tel, contas, gdms_fila

MANAUS = ZoneInfo('America/Manaus')
SP = ZoneInfo('America/Sao_Paulo')


def test_fusos_validar_descrever_opcoes():
    assert fusos.validar('America/Manaus') == 'America/Manaus'
    assert fusos.validar(' Europe/Lisbon ') == 'Europe/Lisbon'
    assert fusos.validar('') is None and fusos.validar(None) is None and fusos.validar('Marte/Olympus') is None
    assert fusos.descrever(None) == 'Brasília (UTC-3)'
    assert fusos.descrever('America/Rio_Branco') == 'Acre e oeste do Amazonas (UTC-5)'
    assert fusos.descrever('Asia/Kolkata') == 'Asia/Kolkata (UTC+5:30)'
    grupos = fusos.opcoes()
    assert grupos[0][0] == 'Brasil' and grupos[0][1][0][0] == 'America/Sao_Paulo'
    nomes = {n for _, itens in grupos for n, _ in itens}
    assert {'America/Manaus', 'Europe/Lisbon', 'Asia/Tokyo'} <= nomes and 'Etc/GMT+3' not in nomes


def _familia(app, email='mae@x.com'):
    with app.engine.begin() as conn:
        return conn.execute(select(db.familias).where(db.familias.c.email == email)).mappings().first()


def test_cadastro_guarda_fuso_sugerido_pelo_navegador(client, app):
    import re
    post(client, '/cadastrar', email='am@x.com', senha='senha12345', senha2='senha12345', nome='A', fuso='America/Manaus')
    codigo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('am@x.com')['corpo']).group(1)
    assert post(client, '/verificar-email', codigo=codigo).status_code == 302
    assert _familia(app, 'am@x.com')['fuso'] == 'America/Manaus'


def test_cadastro_sem_fuso_ou_com_lixo_fica_no_padrao(client, app):
    import re
    post(client, '/cadastrar', email='x@x.com', senha='senha12345', senha2='senha12345', nome='A', fuso='<script>')
    codigo = re.search(r'\b(\d{6})\b', app.mailer.ultimo_para('x@x.com')['corpo']).group(1)
    post(client, '/verificar-email', codigo=codigo)
    assert _familia(app, 'x@x.com')['fuso'] is None
    assert fusos.zona(None).key == fusos.PADRAO


def test_pagina_fuso_troca_e_audita(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    r = client.get(f'/crianca/{cid}/horarios')
    assert 'Brasília (UTC-3)' in r.data.decode()
    r = client.get('/fuso')
    assert 'Mato Grosso' in r.data.decode() and 'Europe' in r.data.decode()
    r = post(client, f'/fuso?crianca_id={cid}', follow_redirects=True, fuso='America/Cuiaba')
    assert 'Mato Grosso (UTC-4)' in r.data.decode()
    assert _familia(app)['fuso'] == 'America/Cuiaba'
    fam = _familia(app)
    assert 'fuso_alterado' in acoes(app, 'familia', fam['id'])
    r = post(client, '/fuso', follow_redirects=True, fuso='Lua/Tranquilidade')
    assert 'Escolha um fuso' in r.data.decode()
    assert _familia(app)['fuso'] == 'America/Cuiaba'
    # sem telefone no GDMS nada entra na fila
    with app.engine.begin() as conn:
        assert gdms_fila.atualizar_relogio(conn, cid) is False
    # o fuso sai na exportacao LGPD
    assert client.get('/meus-dados.json').get_json()['responsavel']['fuso'] == 'America/Cuiaba'


def test_xml_do_telefone_usa_fuso_da_familia(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    c = crianca_row(app, cid)
    tel = {'id': 999999, 'crianca_id': c['id'], 'mac': '000B82AABBCC', 'modelo': 'grp', 'admin_senha': 'abc12345xy', 'xml_versao': 1}
    with app.engine.begin() as conn:
        xml_sp = svc_tel.gerar_xml(conn, tel, app.cfg)
        contas.definir_fuso(conn, c['familia_id'], 'America/Manaus')
        xml_am = svc_tel.gerar_xml(conn, tel, app.cfg)
        contas.definir_fuso(conn, c['familia_id'], 'Europe/Lisbon')
        xml_pt = svc_tel.gerar_xml(conn, tel, app.cfg)
    assert '<P246>UTC+3</P246>' in xml_sp and '<P64>customize</P64>' in xml_sp and '<P143>0</P143>' in xml_sp
    assert '<P246>UTC+4</P246>' in xml_am
    assert '<P246>WET+0WEST-1,M3.5.0/1,M10.5.0</P246>' in xml_pt


def test_horarios_sao_conferidos_no_fuso_da_casa(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    c = crianca_row(app, cid)
    with app.engine.begin() as conn:
        horarios.salvar(conn, c['id'], [{'inicio': '10:00', 'fim': '12:00', 'dias': [0]}], c['familia_id'])
    seg_1230_sp = datetime(2026, 10, 26, 12, 30, tzinfo=SP)   # 11:30 em Manaus
    seg_1330_sp = datetime(2026, 10, 26, 13, 30, tzinfo=SP)   # 12:30 em Manaus
    with app.engine.begin() as conn:
        assert not horarios.dentro_do_horario(conn, c['id_rede'], seg_1230_sp)          # Brasilia: 12:30, fora
        contas.definir_fuso(conn, c['familia_id'], 'America/Manaus')
        assert horarios.dentro_do_horario(conn, c['id_rede'], seg_1230_sp)              # Manaus: 11:30, dentro
        assert not horarios.dentro_do_horario(conn, c['id_rede'], seg_1330_sp)
        # o instante pode vir em qualquer fuso (o AGI manda a hora da central): o resultado e o mesmo
        assert horarios.dentro_do_horario(conn, c['id_rede'], seg_1230_sp.astimezone(ZoneInfo('UTC')))


def test_silenciar_ate_amanha_as_8_no_fuso_da_casa(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    c = crianca_row(app, cid)
    with app.engine.begin() as conn:
        contas.definir_fuso(conn, c['familia_id'], 'America/Manaus')
        ate = horarios.silenciar(conn, c['id'], 'manha', c['familia_id'])
    local = ate.astimezone(MANAUS)
    assert (local.hour, local.minute) == (8, 0)
    assert ate.astimezone(SP).hour == 9
    r = client.get(f'/crianca/{cid}/horarios')
    assert 'às 08:00' in r.data.decode()   # a familia ve a hora da casa dela


def test_filtro_datahora_no_fuso_da_familia(app):
    from flask import g
    f = app.jinja_env.filters['datahora']
    with app.test_request_context('/'):
        assert f('2026-10-26 12:30:00') == '26 out 12:30'
        g.familia = {'fuso': 'America/Manaus'}
        assert f('2026-10-26 12:30:00') == '26 out 11:30'          # texto do Asterisk, gravado em SP
        assert f(datetime(2026, 10, 26, 15, 30, tzinfo=ZoneInfo('UTC'))) == '26 out 11:30'
