"""Modulos puros: ids, grandstream_xml, gdms_client (copiados do prototipo)."""

import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from rede import ids, grandstream_xml as gx, gdms_client as g, auditoria


def test_ids():
    for _ in range(100):
        assert ids.ID_RE.match(ids.gerar_id(lambda x: False))
    assert ids.formatar_id('345678') == '34 56 78'
    assert ids.validar_nick(' Jose07 ') == 'jose07'
    for ruim in ('ab', '7abc', 'ana silva', 'admin', 'ana2015', ''):
        with pytest.raises(ValueError):
            ids.validar_nick(ruim)
    assert ids.classificar_discado('0345678') == ('grupo', '345678')
    assert ids.classificar_discado('9345678') == ('familia1', '345678')
    assert ids.classificar_discado('100') == ('servico', '100')
    assert ids.classificar_discado('045678')[0] == 'invalido'


def test_xml():
    pv = gx.pvalues_sip('h', '345678', 'senha-longa-123', 'a & b', 'gxp')
    pv.update(gx.pvalues_provisionamento('https://p/x?a=1&b=2'))
    raiz = ET.fromstring(gx.gerar_xml('c0:74:ad:01:02:03', pv))
    v = {e.tag: e.text for e in raiz.find('config')}
    assert v['P3'] == 'a & b' and v['P237'] == 'https://p/x?a=1&b=2' and v['P212'] == '2'
    assert v['P145'] == '0' and v['P1414'] == '0' and v['P238'] == '2' and 'P6767' not in v


def test_travas_por_modelo():
    grp = gx.pvalues_travas('senhaadmin123', 'grp')
    ht = gx.pvalues_travas('senhaadmin123', 'ht')
    assert grp['P1357'] == '3' and grp['P22373'] == '1' and grp['P196'] == gx.senha_usuario_aparelho('senhaadmin123')
    assert ht == {'P2': 'senhaadmin123', 'P1650': '0', 'P276': '1'}   # HT80x: sem teclado, so admin/web/ssh
    assert gx.pvalues_provisionamento('http://p/', modelo='ht')['P6767'] == '1'
    assert gx.nome_arquivo('C0:74:AD:01:02:03') == 'cfgc074ad010203.xml'


def test_gdms_assinatura_e_redacao():
    assert g.hash_senha('abc') == hashlib.sha256(hashlib.md5(b'abc').hexdigest().encode()).hexdigest()
    base = g.montar_base_assinatura('T', 'C', 'S', '1', '[]')
    assert base == '&access_token=T&client_id=C&client_secret=S&timestamp=1&' + hashlib.sha256(b'[]').hexdigest() + '&'
    assert g.mac_para_gdms('c074ad010203') == 'C0:74:AD:01:02:03'
    with pytest.raises(ValueError):
        g.corpo_device_add('C074AD010203', 'SN12345678', 'ana silva', 1, 2)
    assert 'siteId' not in g.corpo_device_add('C074AD010203', 'SN12345678', '345678', 0, 2)[0]
    assert g.resultado_device_add({'retCode': 0, 'data': {'success': 1, 'failure': 0}}) == ('ok', None)
    assert g.resultado_device_add({'retCode': 0, 'data': {'success': 0, 'failure': 1, 'errorDeviceList': [{'errorMsg': '30007'}]}}) == ('ja_na_organizacao', '30007')
    assert g.resultado_device_add({'retCode': 40003, 'msg': 'bad signature'})[0] == 'temporario'
    r = auditoria.redigir({'senha_sip': 'x', 'token': 'y', 'ok': {'client_secret': 'z', 'mac': 'm'}})
    assert r == {'senha_sip': '***', 'token': '***', 'ok': {'client_secret': '***', 'mac': 'm'}}


def test_mac_troca_letras_parecidas():
    assert gx.normalizar_mac('c074adla2b3c') == 'C074AD1A2B3C'      # l -> 1
    assert gx.normalizar_mac('C0:74:AD:1A:2B:3C') == 'C074AD1A2B3C'
    assert gx.normalizar_mac('OO:OB:82:AA:BB:CC') == '000B82AABBCC'
    assert gx.normalizar_mac('c074ad0I23S6') == 'C074AD012356'      # I -> 1, S -> 5
    with pytest.raises(ValueError):
        gx.normalizar_mac('EC74D7774')


def test_variantes_serial():
    from rede.servicos import telefones as svc
    assert svc.variantes_serial('35103ZC1D2') == []                       # sem O/I: nada a tentar
    assert svc.variantes_serial('351O3ZC1D2') == ['35103ZC1D2']
    v = svc.variantes_serial('3510IZCOD2')
    assert v == ['35101ZC0D2', '35101ZCOD2', '3510IZC0D2']                # todas trocadas primeiro
    assert len(svc.variantes_serial('OOOOOOOOII')) == 16                  # limite


def test_pvalues_teclas():
    pv = gx.pvalues_teclas([('beto', '234567')])
    assert pv['P1365'] == '0' and pv['P1467'] == 'beto' and pv['P1468'] == '234567'   # VPK 2 = discagem rapida
    assert pv['P23800'] == '-1' and pv['P23803'] == ''                                  # dinamicas vazias
    assert gx.pvalues_teclas([]) ['P1365'] == '31'                                        # sem amigos: VPK 2 volta a linha
    assert gx.pvalues_teclas([('a', '1')], 'ht') == {}
    tres = gx.pvalues_teclas([('a', '234567'), ('b', '345678'), ('c', '456789'), ('d', '567890')])
    assert tres['P23807'] == '456789' and '567890' not in tres.values()

