"""E7: endpoint cfgMAC.xml com prov_log, token, MAC e estados."""

import xml.etree.ElementTree as ET

from sqlalchemy import text

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, telefone_row, acoes, MAC, SN


def _preparar(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    t = telefone_row(app, cid)
    with app.engine.begin() as c:
        tok = c.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t AND ativo=1'), {'t': t['id']}).scalar()
    return cid, t, tok


def _prov_log(app):
    with app.engine.begin() as c:
        return c.execute(text('SELECT resultado, mac_pedido, xml_versao FROM prov_log ORDER BY id')).all()


def test_entrega_xml_e_transiciona(client, app):
    cid, t, tok = _preparar(client, app)
    r = client.get(f'/p/{tok}/cfgc074ad010203.xml', headers={'User-Agent': 'Grandstream GRP2601 1.0.5.x'})
    assert r.status_code == 200 and r.mimetype == 'text/xml'
    raiz = ET.fromstring(r.data)
    cfg = {e.tag: e.text for e in raiz.find('config')}
    c = crianca_row(app, cid)
    assert raiz.find('mac').text == 'C074AD010203'
    assert cfg['P35'] == c['id_rede'] and cfg['P34'] == c['senha_sip'] and cfg['P3'] == 'jose07'
    assert cfg['P47'] == 'sip.teste' and cfg['P130'] == '1' and cfg['P72'] == '1'
    assert cfg['P237'] == f'https://prov.teste/p/{tok}/'
    assert cfg['P2'] == t['admin_senha']
    # travas oficiais do GRP260x (bancada/referencia-pvalues): menu fechado, reset com senha, so HTTPS, sem SSH
    assert cfg['P1357'] == '3' and cfg['P22373'] == '1' and cfg['P1650'] == '0' and cfg['P8469'] == '0' and cfg['P276'] == '1'
    assert cfg['P196'] and cfg['P196'] != t['admin_senha'] and cfg['P196'].isalnum()
    t2 = telefone_row(app, cid)
    assert t2['estado'] == 'config_entregue' and t2['ultimo_prov_ua'].startswith('Grandstream')
    assert _prov_log(app) == [('entregue', 'C074AD010203', 1)]
    assert 'telefone_config_entregue' in acoes(app, 'telefone', t['id'])


def test_token_invalido_404_e_logado(client, app):
    _preparar(client, app)
    r = client.get('/p/naoexiste/cfgc074ad010203.xml')
    assert r.status_code == 404
    assert _prov_log(app)[-1][0] == 'token_invalido'


def test_mac_nao_bate_404_sem_mudar_estado(client, app):
    cid, t, tok = _preparar(client, app)
    r = client.get(f'/p/{tok}/cfgc074ad999999.xml')
    assert r.status_code == 404
    assert telefone_row(app, cid)['estado'] == 'aguardando_boot'
    assert _prov_log(app)[-1][0] == 'mac_nao_bate'
    assert 'prov_mac_nao_bate' in acoes(app, 'telefone', t['id'])


def test_token_compartilhado_revoga(client, app):
    cid, t, tok = _preparar(client, app)
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 200
    assert client.get(f'/p/{tok}/cfgc074ad999999.xml').status_code == 404
    # token revogado: o proprio aparelho agora recebe 404 e ha caso
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 404
    with app.engine.begin() as c:
        casos = [r[0] for r in c.execute(text('SELECT tipo FROM casos')).all()]
    assert 'token_compartilhado' in casos
    assert 'alerta_token_compartilhado' in acoes(app, 'telefone', t['id'])


def test_reentrega_nao_regride_estado_e_reconfigurar_sobe_versao(client, app):
    from rede import estados
    cid, t, tok = _preparar(client, app)
    client.get(f'/p/{tok}/cfgc074ad010203.xml')
    with app.engine.begin() as c:
        estados.transicionar(c, t['id'], 'sip_registrado', 'telefone', 'x')
    client.get(f'/p/{tok}/cfgc074ad010203.xml')
    assert telefone_row(app, cid)['estado'] == 'registrado'
    assert 'config_reentregue' in acoes(app, 'telefone', t['id'])
    senha_antes = crianca_row(app, cid)['senha_sip']
    post(client, f'/crianca/{cid}/telefone', acao='reconfigurar')
    r = client.get(f'/p/{tok}/cfgc074ad010203.xml')
    raiz = ET.fromstring(r.data)
    assert raiz.find('config').get('version') == '2'
    assert crianca_row(app, cid)['senha_sip'] != senha_antes
    cfg = {e.tag: e.text for e in raiz.find('config')}
    assert cfg['P34'] == crianca_row(app, cid)['senha_sip']


def test_desativado_nao_recebe_xml(client, app):
    cid, t, tok = _preparar(client, app)
    post(client, f'/crianca/{cid}/telefone', acao='remover')
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 404
    assert _prov_log(app)[-1][0] == 'token_invalido'   # token revogado


def test_arquivos_genericos_404(client, app):
    cid, t, tok = _preparar(client, app)
    assert client.get(f'/p/{tok}/cfg.xml').status_code == 404
    assert client.get(f'/p/{tok}/').status_code == 404


def test_modelo_wifi_muda_o_passo_ligar(client, app):
    from conftest import cadastrar_e_entrar, criar_crianca, post, MAC, SN
    from rede.servicos import telefones
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'wifi01')
    r = client.get(f'/crianca/{cid}/telefone')
    assert b'id="modelo-grpw"' in r.data and b'GRP2602W' in r.data and b'GRP2601' in r.data
    r = post(client, f'/crianca/{cid}/telefone', acao='informar', serial=SN, mac=MAC, modelo='xx', follow_redirects=True)
    assert 'Escolha o modelo'.encode() in r.data
    r = post(client, f'/crianca/{cid}/telefone', acao='informar', serial=SN, mac=MAC, modelo='grpw', follow_redirects=True)
    assert r.status_code == 200
    with app.engine.begin() as c:
        tel = telefones.atual_da_crianca(c, cid)
        assert tel['modelo'] == 'grpw'
        # XML do grpw = mesmos P-values do grp
        from rede import grandstream_xml as gx
        assert gx.pvalues_sip('h', '234567', 's' * 12, 'n', 'grpw')['P47'] == 'h'
    # simulado: fila anda ate aguardando_boot e a tela mostra o Wi-Fi
    for _ in range(3):
        with app.engine.begin() as c:
            from rede.servicos import gdms_fila
            gdms_fila.processar(c, app.cfg)
    r = client.get(f'/crianca/{cid}/telefone')
    with app.engine.begin() as c:
        tel = telefones.atual_da_crianca(c, cid)
        st = telefones.status(c, tel, app.cfg)
    assert st['wifi'] and 'Wi-Fi' in st['passos'][3]['titulo']
    if st['estado'] == 'aguardando_boot':
        assert b'Conectar ao Wi-Fi' in r.data and b'Wi-Fi Settings' in r.data and b'Internet.' not in r.data
