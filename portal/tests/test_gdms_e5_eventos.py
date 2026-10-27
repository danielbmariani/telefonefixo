"""E5 por API (device/config/xml) com HTTP falso, retentativa so da etapa de configuracao,
webhook de eventos do GDMS, e funcoes puras de assinatura de formulario."""

import json
from datetime import timedelta

from sqlalchemy import text

from conftest import acoes
from rede import gdms_client
from rede.config import Config
from rede.servicos import contas, criancas, telefones, gdms_fila, gdms_eventos
from rede.tempo import agora

SEGREDO = 's' * 40


def _cfg(app, **extra):
    base = dict(AMBIENTE='teste', DATABASE_URL=app.cfg.DATABASE_URL, GDMS_MODO='real', GDMS_ENVIO_MODO='api',
                GDMS_CLIENT_ID='cid', GDMS_CLIENT_SECRET='sec', GDMS_USERNAME='u', GDMS_PASSWORD='p',
                GDMS_ORG_ID='123456', GDMS_SITE_ID='0', GDMS_MAX_TENTATIVAS='2', PROV_URL='https://prov.teste',
                SIP_HOST='sip.teste', MAIL_BACKEND='memoria')
    base.update(extra)
    return Config(env={}, **base)


def _http(chamadas, falhar_config=False):
    def http_falso(metodo, url, corpo=None, headers=None, timeout=20):
        chamadas.append((url.split('?')[0], headers or {}, corpo))
        if url.endswith('/oapi/oauth/token'):
            return 200, json.dumps({'access_token': 'A', 'refresh_token': 'R'})
        if 'device/list' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'result': [], 'total': 0}})
        if 'device/add' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 1, 'failure': 0, 'errorDeviceList': []}})
        if 'device/config/xml' in url:
            if falhar_config:
                return 200, json.dumps({'retCode': 30014, 'msg': 'device mac not exists', 'data': ''})
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': ''})
        return 200, '{}'
    return http_falso


def test_e5_por_api_envia_xml_e_fica_aguardando_boot(app):
    cfg = _cfg(app)
    chamadas = []
    with app.engine.begin() as conn, app.app_context():
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000011', 'SN00000011', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=_http(chamadas))
        tel = telefones.por_id(conn, t['id'])
        assert tel['estado'] == 'aguardando_boot' and tel['config_enviada_em'] is not None
        fila = conn.execute(text('SELECT estado, etapa, tentativas FROM gdms_fila')).all()
        assert fila == [('ok', 'cadastro', 0)]
        assert conn.execute(text("SELECT count(*) FROM tarefas")).scalar() == 0
        # a chamada multipart foi feita com o XML "ponteiro": tem P237 e nao tem a senha SIP
        url, headers, corpo = [c for c in chamadas if c[0].endswith('device/config/xml')][0]
        assert headers['Content-Type'].startswith('multipart/form-data; boundary=')
        assert b'<P237>https://prov.teste/p/' in corpo and b'<P34>' not in corpo and b'<P2>' in corpo
        assert b'name="mac"\r\n\r\nC0:74:AD:00:00:11' in corpo and b'name="applyConfig"\r\n\r\ntrue' in corpo
        # gdms_log guarda md5/tamanho do arquivo, nao o conteudo
        glog = conn.execute(text("SELECT corpo_enviado FROM gdms_log WHERE endpoint='device/config/xml'")).all()
        assert 'md5' in json.dumps(glog[0][0]) and 'P237' not in json.dumps(glog[0][0])
    a = acoes(app, 'telefone', t['id'])
    assert a[:3] == ['telefone_dados_informados', 'telefone_gdms_ok', 'telefone_config_enviada']
    assert app.mailer.enviados[-1]['para'] == 'f@x.com' and 'pode ligar' in app.mailer.enviados[-1]['assunto'].lower()


def test_e5_falha_retenta_so_config_e_depois_tarefa_manual(app):
    cfg = _cfg(app)
    chamadas = []
    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000012', 'SN00000012', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=_http(chamadas, falhar_config=True))
        assert telefones.por_id(conn, t['id'])['estado'] == 'gdms_cadastrado'
        fila = conn.execute(text('SELECT estado, etapa, tentativas, ultimo_ret_code FROM gdms_fila')).all()
        assert fila == [('pendente', 'config', 1, 30014)]
        n_add = len([c for c in chamadas if c[0].endswith('device/add')])
        # segunda rodada: nao repete device/add, so o config/xml; estoura o maximo (2) -> tarefa manual
        gdms_fila.processar(conn, cfg, http=_http(chamadas, falhar_config=True), ref=agora() + timedelta(hours=1))
        assert len([c for c in chamadas if c[0].endswith('device/add')]) == n_add
        assert len([c for c in chamadas if c[0].endswith('device/config/xml')]) == 2
        assert conn.execute(text('SELECT estado, etapa FROM gdms_fila')).all() == [('erro', 'config')]
        tarefas = conn.execute(text("SELECT tipo, descricao FROM tarefas WHERE estado='aberta'")).all()
        assert tarefas[0][0] == 'enviar_config_gdms' and '30014' in tarefas[0][1]
        assert telefones.por_id(conn, t['id'])['estado'] == 'gdms_cadastrado'
    a = acoes(app, 'telefone', t['id'])
    assert 'gdms_config_retentativa' in a and 'tarefa_operador_criada' in a


def test_xml_gdms_completo_leva_conta_sip(app):
    cfg = _cfg(app, GDMS_XML_CONTEUDO='completo')
    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000013', 'SN00000013', '1.1.1.1', cfg, familia_id=fid)
        xml = telefones.gerar_xml_gdms(conn, telefones.por_id(conn, t['id']), cfg)
        assert '<P34>' in xml and '<P237>' in xml and f'<P35>{cr["id_rede"]}</P35>' in xml


def test_webhook_gdms(client, app):
    app.cfg.GDMS_WEBHOOK_SEGREDO = SEGREDO
    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', app.cfg)
        t = telefones.informar(conn, cr, 'C074AD000014', 'SN00000014', '1.1.1.1', app.cfg, familia_id=fid)
    # segredo errado: 404 e nada gravado
    r = client.post('/gdms/eventos/errado', json={'messages': []})
    assert r.status_code == 404
    msgs = [
        {'type': 1, 'enterpriseId': 1, 'projectId': 1, 'orgId': 123456, 'mac': 'C0:74:AD:00:00:14', 'statusType': 0, 'deviceStatus': 1},
        {'type': 1, 'orgId': 123456, 'mac': 'C0:74:AD:00:00:14', 'statusType': 1, 'accountIndex': 1,
         'userId': cr['id_rede'], 'accountStatus': 'Up'},
        {'type': 2, 'orgId': 123456, 'mac': 'C0:74:AD:00:00:14', 'alertType': 2, 'level': 3, 'messageType': 1},
        {'type': 1, 'orgId': 123456, 'mac': 'C0:74:AD:00:00:99', 'statusType': 0, 'deviceStatus': 1},
        'lixo',
    ]
    r = client.post(f'/gdms/eventos/{SEGREDO}', json={'messages': msgs})
    assert r.status_code == 200 and r.get_json()['retCode'] == 0
    assert r.get_json()['data'] == {'recebidas': 4, 'desconhecidas': 1, 'ignoradas': 1, 'online': 1, 'offline': 0, 'conta_up': 1, 'alertas': 1}
    with app.engine.begin() as conn:
        tel = telefones.por_id(conn, t['id'])
        assert tel['gdms_online_em'] is not None and tel['gdms_conta_up_em'] is not None
        assert tel['estado'] == 'dados_informados'   # evento do GDMS nao muda estado
        assert conn.execute(text("SELECT count(*) FROM gdms_log WHERE endpoint='callback'")).scalar() == 4
        # primeiro boot de fabrica: o GRP2601 manda "factory reset" junto com online/reboot -> so audit
        assert conn.execute(text("SELECT count(*) FROM casos WHERE tipo='reset_de_fabrica'")).scalar() == 0
        conn.execute(text("UPDATE telefones SET config_entregue_em=:a, registrado_em=:a WHERE id=:i"), {'a': agora(), 'i': t['id']})
    client.post(f'/gdms/eventos/{SEGREDO}', json={'messages': [msgs[2]]})   # config recente: ainda e o primeiro boot
    with app.engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM casos WHERE tipo='reset_de_fabrica'")).scalar() == 0
        conn.execute(text("UPDATE telefones SET config_entregue_em=:a WHERE id=:i"), {'a': agora() - timedelta(minutes=30), 'i': t['id']})
    # telefone conectado ha tempo: o mesmo alerta vira caso; repetido nao duplica
    client.post(f'/gdms/eventos/{SEGREDO}', json={'messages': [msgs[2]]})
    client.post(f'/gdms/eventos/{SEGREDO}', json={'messages': [msgs[2]]})
    with app.engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM casos WHERE tipo='reset_de_fabrica'")).scalar() == 1
    a = acoes(app, 'telefone', t['id'])
    assert 'gdms_aparelho_online' in a and 'gdms_conta_up' in a and 'gdms_alerta_reset_de_fabrica' in a
    # sem segredo configurado, o endpoint nao existe
    app.cfg.GDMS_WEBHOOK_SEGREDO = ''
    assert client.post(f'/gdms/eventos/{SEGREDO}', json={'messages': []}).status_code == 404


def test_assinatura_formulario_segue_o_guia():
    # Signature Method, item 4: campos + md5 do arquivo, em ordem alfabetica
    base = gdms_client.montar_base_formulario('T', 'C', 'S', '1570615320000', {'is_save': 1}, {'cfg_file': ('a.xml', b'abc')},
                                              params={'name': 'aaaaa'})
    assert base == ('&access_token=T&cfg_file=900150983cd24fb0d6963f7d28e17f72&client_id=C&client_secret=S'
                    '&is_save=1&name=aaaaa&timestamp=1570615320000&')
    corpo = gdms_client.montar_multipart({'mac': 'X'}, {'xml': ('cfg.xml', b'<x/>')}, 'B')
    assert corpo.startswith(b'--B\r\nContent-Disposition: form-data; name="mac"\r\n\r\nX\r\n--B\r\n') and corpo.endswith(b'--B--\r\n')
    assert gdms_client.resultado_simples({'retCode': 0, 'msg': ''}) == (True, 0, '')
    assert gdms_client.resultado_simples({'retCode': 30014, 'msg': 'device mac not exists'})[0] is False
    assert gdms_client.resultado_simples(None)[0] is False


def test_registrar_assinatura_exige_segredo(app):
    class Cli:
        def definir_callback(self, url):
            self.url = url; return {'retCode': 0}
        def assinar_eventos(self, org):
            self.org = org; return {'retCode': 0}
    cfg = _cfg(app, GDMS_WEBHOOK_SEGREDO='curto', SITE_URL='https://rede.teste')
    try:
        gdms_eventos.registrar_assinatura(Cli(), cfg)
        assert False
    except ValueError:
        pass
    cfg = _cfg(app, GDMS_WEBHOOK_SEGREDO=SEGREDO, SITE_URL='https://rede.teste')
    c = Cli()
    gdms_eventos.registrar_assinatura(c, cfg)
    assert c.url == f'https://rede.teste/gdms/eventos/{SEGREDO}' and c.org == 123456


def test_reenviar_config_para_telefone_registrado(app):
    cfg = _cfg(app)
    chamadas = []
    with app.engine.begin() as conn, app.app_context():
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000012', 'SN00000012', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=_http(chamadas))
        conn.execute(text("UPDATE telefones SET estado='registrado' WHERE id=:i"), {'i': t['id']})
        gdms_fila.reenviar_config(conn, t['id'])
        n_antes = len(chamadas)
        gdms_fila.processar(conn, cfg, http=_http(chamadas))
        tel = telefones.por_id(conn, t['id'])
        fila = conn.execute(text('SELECT estado, etapa FROM gdms_fila WHERE telefone_id=:i ORDER BY id'), {'i': t['id']}).all()
    assert tel['estado'] == 'registrado'                       # reenvio nao mexe no estado
    assert fila == [('ok', 'cadastro'), ('ok', 'config')]
    assert [c[0] for c in chamadas[n_antes:] if 'config/xml' in c[0]]   # device/config/xml foi chamado de novo
    assert 'gdms_config_reenviada' in acoes(app, 'telefone', t['id'])


def test_serial_com_letra_o_e_corrigido_pelo_gdms(app):
    cfg = _cfg(app)
    chamadas = []
    CERTO = 'SN0000O012'.replace('O', '0')      # etiqueta diz SN00000012; familia digitou com a letra O

    def http_falso(metodo, url, corpo=None, headers=None, timeout=20):
        chamadas.append((url.split('?')[0], headers or {}, corpo))
        if url.endswith('/oapi/oauth/token'):
            return 200, json.dumps({'access_token': 'A', 'refresh_token': 'R'})
        if 'device/list' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'result': [], 'total': 0}})
        if 'device/add' in url:
            sn = json.loads(corpo)[0]['sn'] if isinstance(corpo, (str, bytes)) else ''
            if sn == CERTO:
                return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 1, 'failure': 0, 'errorDeviceList': []}})
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 0, 'failure': 1,
                                                                      'errorDeviceList': [{'mac': 'x', 'errorMsg': '30010'}]}})
        if 'device/config/xml' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': ''})
        return 200, json.dumps({'retCode': 0, 'msg': '', 'data': ''})

    with app.engine.begin() as conn, app.app_context():
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000013', 'SN0000O012', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=http_falso)
        tel = telefones.por_id(conn, t['id'])
    assert tel['serial'] == CERTO and tel['estado'] == 'aguardando_boot'
    assert len([c for c in chamadas if 'device/add' in c[0]]) == 2
    assert 'serial_corrigido_automaticamente' in acoes(app, 'telefone', t['id'])


def test_amizade_aceita_reenvia_teclas_pelo_gdms(app):
    cfg = _cfg(app)
    chamadas = []
    with app.engine.begin() as conn, app.app_context():
        fa = contas.criar_operador(conn, 'fa@x.com', 'senha12345', 'A', 'familia')
        fb = contas.criar_operador(conn, 'fb@x.com', 'senha12345', 'B', 'familia')
        ca = criancas.criar(conn, fa, 'ana', cfg)
        cb = criancas.criar(conn, fb, 'beto', cfg)
        t = telefones.informar(conn, ca, 'C074AD000021', 'SN00000021', '1.1.1.1', cfg, familia_id=fa)
        gdms_fila.processar(conn, cfg, http=_http(chamadas))
        conn.execute(text("UPDATE telefones SET estado='registrado' WHERE id=:i"), {'i': t['id']})
        from rede.servicos import amizades
        ped = amizades.pedir(conn, cb, ca['id_rede'], fb, cfg)
        amizades.responder(conn, ped['id'], fa, 'aceitar')
        n = len(chamadas)
        gdms_fila.processar(conn, cfg, http=_http(chamadas))
        fila = conn.execute(text("SELECT etapa, estado FROM gdms_fila WHERE telefone_id=:i ORDER BY id"), {'i': t['id']}).all()
    assert ('teclas', 'ok') in fila
    corpo = [c[2] for c in chamadas[n:] if 'config/xml' in c[0]][0]
    assert b'<P1468>' + cb['id_rede'].encode() + b'</P1468>' in corpo and b'<P1467>beto</P1467>' in corpo and b'<P34>' not in corpo
    assert 'gdms_teclas_enviadas' in acoes(app, 'telefone', t['id'])

