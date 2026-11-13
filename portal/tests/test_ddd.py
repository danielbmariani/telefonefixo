"""DDD da casa (rede/ddd.py, doc 20): base de municipios, DDD por cidade e por coordenadas, por IP (GeoLite2
simulado), sugestao nas quatro fontes e o que a crianca disca."""

from sqlalchemy import insert, text

from conftest import cadastrar_e_entrar, criar_crianca, crianca_row
from rede import db, ddd, geoip
from rede.servicos import familia_telefones as fam, contas
from rede.tempo import agora

SP = {'lat': -23.5329, 'lon': -46.6395}
CAMPINAS = {'lat': -22.9053, 'lon': -47.0659}


def test_base_de_municipios_cobre_os_67_ddds_e_as_cidades_dos_rotulos():
    ms = ddd.municipios()
    assert len(ms) > 5500
    assert {m['ddd'] for m in ms} == set(ddd.DDDS) and len(ddd.DDDS) == 67
    assert all(m['uf'] for m in ms)
    for d, cidade in ddd.ROTULOS.items():
        achados = [m for m in ms if m['chave'] == ddd._sem_acento(cidade)]
        assert any(m['ddd'] == d for m in achados), (d, cidade)
    assert ddd.rotulo('19') == 'Campinas e região' and ddd.opcoes()[0] == ('11', 'São Paulo e região')


def test_validar():
    assert ddd.validar('11') == '11' and ddd.validar(' 19 ') == '19' and ddd.validar(19) == '19'
    for ruim in ('10', '20', '1', '111', '', None, 'ab'):
        assert ddd.validar(ruim) is None


def test_por_cidade_e_por_coordenadas():
    assert ddd.por_cidade('são paulo', 'SP')['ddd'] == '11'
    assert ddd.por_cidade('Sao Paulo')['ddd'] == '11'          # sem acento, sem UF: so existe um
    assert ddd.por_cidade('Campinas', 'SP')['ddd'] == '19'
    assert ddd.por_cidade('Bom Jesus') is None                  # varios estados: sem UF nao desempata
    assert ddd.por_cidade('Bom Jesus', 'PI')['ddd'] == '89'
    assert ddd.por_cidade('', 'SP') is None and ddd.por_cidade('Xyzlandia', 'SP') is None
    m, dist = ddd.por_coordenadas(**SP)
    assert m['ddd'] == '11' and dist < 5
    assert ddd.por_coordenadas(**CAMPINAS)[0]['ddd'] == '19'
    assert ddd.por_coordenadas(-30.03, -51.23)[0]['ddd'] == '51'   # Porto Alegre


def test_por_ip_usa_a_cidade_antes_das_coordenadas(app, monkeypatch):
    regs = {
        '1.1.1.1': {'pais': 'BR', 'cidade': 'Campinas', 'uf': 'SP', 'raio_km': 10, **SP},   # nome vale mais que o ponto
        '2.2.2.2': {'pais': 'BR', 'cidade': None, 'uf': 'SP', 'raio_km': 100, **SP},
        '3.3.3.3': {'pais': 'PT', 'cidade': 'Lisboa', 'uf': None, 'raio_km': 5, 'lat': 38.7, 'lon': -9.1},
        '4.4.4.4': {'pais': 'BR', 'cidade': 'Cidade Inventada', 'uf': 'SP', 'raio_km': 20, **CAMPINAS},
        '5.5.5.5': {'pais': 'BR', 'cidade': None, 'uf': None, 'raio_km': None, 'lat': None, 'lon': None},
    }
    monkeypatch.setattr(geoip, 'registro', lambda ip, cfg: regs.get(ip))
    assert ddd.por_ip('1.1.1.1', app.cfg) == {'ddd': '19', 'municipio': 'Campinas', 'uf': 'SP', 'raio_km': 10, 'como': 'cidade'}
    assert ddd.por_ip('2.2.2.2', app.cfg)['ddd'] == '11' and ddd.por_ip('2.2.2.2', app.cfg)['como'] == 'proximo'
    assert ddd.por_ip('3.3.3.3', app.cfg) is None
    assert ddd.por_ip('4.4.4.4', app.cfg)['ddd'] == '19' and ddd.por_ip('4.4.4.4', app.cfg)['como'] == 'proximo'
    assert ddd.por_ip('5.5.5.5', app.cfg) is None and ddd.por_ip('9.9.9.9', app.cfg) is None


def test_geoip_registro_sem_base_devolve_none(app):
    assert geoip.registro('200.160.2.3', app.cfg) is None
    assert geoip.registro('10.0.0.1', app.cfg) is None and geoip.registro('x', app.cfg) is None


def test_sugerir_na_ordem_familia_celulares_telefone_navegador(client, app, monkeypatch):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    fid = crianca_row(app, cid)['familia_id']
    regs = {'7.7.7.7': {'pais': 'BR', 'cidade': 'Campinas', 'uf': 'SP', 'raio_km': 10, **CAMPINAS},
            '8.8.8.8': {'pais': 'BR', 'cidade': 'Porto Alegre', 'uf': 'RS', 'raio_km': 80, 'lat': -30.03, 'lon': -51.23}}
    monkeypatch.setattr(geoip, 'registro', lambda ip, cfg: regs.get(ip))
    with app.engine.begin() as c:
        # nada: sem sugestao
        assert ddd.sugerir(c, fid, app.cfg) == (None, None, None)
        # IP do navegador
        d, origem, lugar = ddd.sugerir(c, fid, app.cfg, ip_navegador='8.8.8.8')
        assert (d, origem, lugar) == ('51', 'navegador_ip', {'municipio': 'Porto Alegre', 'uf': 'RS', 'raio_km': 80})
        assert ddd.descrever_origem(origem, lugar) == 'pelo seu acesso agora, a casa parece estar perto de Porto Alegre, RS'
        # telefone da crianca ganha do navegador
        c.execute(insert(db.telefones).values(crianca_id=cid, mac='C074AD010203', serial='SN1', modelo='grp', estado='ativo',
                                              admin_senha='x', informado_em=agora(), ultimo_prov_em=agora(), ultimo_prov_ip='7.7.7.7'))
        d, origem, lugar = ddd.sugerir(c, fid, app.cfg, ip_navegador='8.8.8.8')
        assert (d, origem) == ('19', 'telefone_ip')
        assert ddd.descrever_origem(origem, lugar, 'ana01') == 'pelo telefone de ana01, a casa parece estar em Campinas, SP'
        # celulares de casa ganham do IP
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        assert ddd.sugerir(c, fid, app.cfg, ip_navegador='8.8.8.8')[:2] == ('11', 'celulares')
        fam.adicionar(c, fid, '21912345678', 'Vó', atalho=False)
        fam.adicionar(c, fid, '21933334444', 'Tio', atalho=False)
        assert ddd.ddd_dos_celulares(c, fid) == '11'            # celular de casa pesa 2; dois outros de 21 pesam 2: empate vai para o de casa
        fam.adicionar(c, fid, '21955556666', 'Tia', atalho=False)
        assert ddd.ddd_dos_celulares(c, fid) == '21'
        # escolha da familia ganha de tudo
        assert contas.definir_ddd(c, fid, '19') == '19'
        assert ddd.sugerir(c, fid, app.cfg, ip_navegador='8.8.8.8') == ('19', 'familia', None)
        assert ddd.ddd_da_familia(c, fid) == '19'
        assert c.execute(text('SELECT ddd_origem FROM familias WHERE id=:f'), {'f': fid}).scalar() == 'familia'
        assert ddd.descrever_origem('familia', None) == 'escolhido por você'


def test_formatar_discagem_e_parte_local():
    assert ddd.formatar_discagem('1134567890', '11') == '3456 7890'
    assert ddd.formatar_discagem('11987654321', '11') == '98765 4321'
    assert ddd.formatar_discagem('1934567890', '11') == '19 3456 7890'
    assert ddd.formatar_discagem('1134567890', None) == '11 3456 7890'
    assert ddd.formatar_discagem('', '11') == '' and ddd.formatar_discagem('123', '11') == '123'
    assert ddd.parte_local('1134567890') == '34567890'
