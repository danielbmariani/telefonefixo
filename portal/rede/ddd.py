"""
ddd.py — DDD da casa e discagem dos telefones da família (doc 20).

A criança disca só o número quando o telefone é do DDD da casa e DDD + número quando é de fora (sem 0,
sem código de operadora). A central não depende do DDD da casa para completar: ela casa o discado com a
lista da família pelo fim do número (familia_telefones.casar_discado); o DDD da casa só desempata e serve
para a família cadastrar sem DDD e para imprimir a lista do jeito que a criança disca.

Fontes do DDD da casa, nesta ordem (decisão do Daniel, 13/11/2026): o que a família escolheu
(familias.ddd); o DDD dos celulares já cadastrados; o IP de onde o telefone da criança busca a
configuração (GeoLite2, rede/geoip.py) convertido em DDD pelo município (rede/dados/municipios.csv,
base de Kelvin S. do Prado, MIT); o IP do navegador do responsável. Nenhuma sugestão é gravada em
silêncio: a família vê e confirma.
"""

import csv
import math
import os
import threading
import unicodedata

from sqlalchemy import select, and_

DDDS = frozenset(
    '11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 46 47 48 49 '
    '51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 '
    '91 92 93 94 95 96 97 98 99'.split())

# Cidade de referencia de cada DDD, para o rotulo "11 São Paulo e região". Conferido contra a base de municipios
# no teste (cada cidade existe com esse DDD).
ROTULOS = {
    '11': 'São Paulo', '12': 'São José dos Campos', '13': 'Santos', '14': 'Bauru', '15': 'Sorocaba',
    '16': 'Ribeirão Preto', '17': 'São José do Rio Preto', '18': 'Presidente Prudente', '19': 'Campinas',
    '21': 'Rio de Janeiro', '22': 'Campos dos Goytacazes', '24': 'Volta Redonda', '27': 'Vitória',
    '28': 'Cachoeiro de Itapemirim', '31': 'Belo Horizonte', '32': 'Juiz de Fora', '33': 'Governador Valadares',
    '34': 'Uberlândia', '35': 'Poços de Caldas', '37': 'Divinópolis', '38': 'Montes Claros', '41': 'Curitiba',
    '42': 'Ponta Grossa', '43': 'Londrina', '44': 'Maringá', '45': 'Foz do Iguaçu', '46': 'Francisco Beltrão',
    '47': 'Joinville', '48': 'Florianópolis', '49': 'Chapecó', '51': 'Porto Alegre', '53': 'Pelotas',
    '54': 'Caxias do Sul', '55': 'Santa Maria', '61': 'Brasília', '62': 'Goiânia', '63': 'Palmas', '64': 'Rio Verde',
    '65': 'Cuiabá', '66': 'Rondonópolis', '67': 'Campo Grande', '68': 'Rio Branco', '69': 'Porto Velho',
    '71': 'Salvador', '73': 'Ilhéus', '74': 'Juazeiro', '75': 'Feira de Santana', '77': 'Vitória da Conquista',
    '79': 'Aracaju', '81': 'Recife', '82': 'Maceió', '83': 'João Pessoa', '84': 'Natal', '85': 'Fortaleza',
    '86': 'Teresina', '87': 'Petrolina', '88': 'Juazeiro do Norte', '89': 'Picos', '91': 'Belém', '92': 'Manaus',
    '93': 'Santarém', '94': 'Marabá', '95': 'Boa Vista', '96': 'Macapá', '97': 'Coari', '98': 'São Luís',
    '99': 'Imperatriz',
}

# codigo_uf do IBGE -> sigla (o CSV traz o codigo; o GeoLite2 traz a sigla)
UFS = {'11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI',
       '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES',
       '33': 'RJ', '35': 'SP', '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF'}

RAIO_CONFIAVEL_KM = 50   # acima disso a sugestao e "parece estar perto de"

_CSV = os.path.join(os.path.dirname(__file__), 'dados', 'municipios.csv')
_trava = threading.Lock()
_municipios = None


def validar(ddd):
    """'11' -> '11'; qualquer outra coisa -> None."""
    d = ''.join(ch for ch in str(ddd or '') if ch.isdigit())
    return d if d in DDDS else None


def rotulo(ddd):
    """'19' -> 'Campinas e região'."""
    return f'{ROTULOS[ddd]} e região' if ddd in ROTULOS else ''


def opcoes():
    """[(ddd, 'Campinas e região'), ...] em ordem numerica, para o <select>."""
    return [(d, rotulo(d)) for d in sorted(DDDS)]


def _sem_acento(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', (texto or '').lower()) if not unicodedata.combining(c)).strip()


def municipios():
    """Lista de dicts (nome, chave, uf, lat, lon, ddd), lida do CSV uma vez."""
    global _municipios
    with _trava:
        if _municipios is None:
            lidos = []
            with open(_CSV, encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    lidos.append({'nome': r['nome'], 'chave': _sem_acento(r['nome']), 'uf': UFS.get(r['codigo_uf'], ''),
                                  'lat': float(r['latitude']), 'lon': float(r['longitude']), 'ddd': r['ddd'].strip()})
            _municipios = lidos
        return _municipios


def por_cidade(nome, uf=None):
    """Municipio com esse nome (sem acento, sem caixa) e, se dada, essa UF. None se nao achar ou se houver mais de um
    com o mesmo nome e a UF nao desempatar."""
    chave = _sem_acento(nome)
    if not chave:
        return None
    iguais = [m for m in municipios() if m['chave'] == chave and (not uf or m['uf'] == (uf or '').upper())]
    return iguais[0] if len(iguais) == 1 else None


def por_coordenadas(lat, lon):
    """Municipio mais proximo do ponto (distancia equirretangular, suficiente para escolher o vizinho) e a distancia
    em km ate a sede dele."""
    k = math.cos(math.radians(lat))
    melhor = min(municipios(), key=lambda m: (m['lat'] - lat) ** 2 + ((m['lon'] - lon) * k) ** 2)
    dist = math.hypot((melhor['lat'] - lat) * 111.0, (melhor['lon'] - lon) * 111.0 * k)
    return melhor, dist


def por_ip(ip, cfg):
    """IP publico -> {'ddd', 'municipio', 'uf', 'raio_km', 'como'} ou None (fora do Brasil, IP privado, sem base).
    Primeiro pelo nome da cidade que o GeoLite2 traz (perto de uma divisa de DDD o nome vale mais que o ponto),
    depois pelo municipio mais proximo das coordenadas."""
    from . import geoip
    reg = geoip.registro(ip, cfg)
    if not reg or reg.get('pais') != 'BR':
        return None
    raio = reg.get('raio_km')
    m = por_cidade(reg.get('cidade'), reg.get('uf')) if reg.get('cidade') else None
    como = 'cidade'
    if not m and reg.get('lat') is not None and reg.get('lon') is not None:
        m, _ = por_coordenadas(reg['lat'], reg['lon'])
        como = 'proximo'
    if not m:
        return None
    return {'ddd': m['ddd'], 'municipio': m['nome'], 'uf': m['uf'], 'raio_km': raio, 'como': como}


def ddd_da_familia(conn, familia_id):
    """DDD escolhido ou confirmado pela familia (familias.ddd), ou None."""
    from . import db
    return validar(conn.execute(select(db.familias.c.ddd).where(db.familias.c.id == familia_id)).scalar())


def ddd_dos_celulares(conn, familia_id):
    """DDD mais frequente entre os telefones cadastrados (celulares de casa primeiro no desempate), ou None."""
    from .servicos import familia_telefones as svc_fam
    tels = svc_fam.listar(conn, familia_id)
    if not tels:
        return None
    contagem = {}
    for t in tels:
        d = t['numero'][:2]
        peso = 2 if t['posicao'] in svc_fam.PREFIXOS else 1
        contagem[d] = contagem.get(d, 0) + peso
    return validar(max(contagem, key=lambda d: (contagem[d], d == tels[0]['numero'][:2])))


def ip_do_telefone(conn, familia_id):
    """IP publico de onde o telefone mais recente da familia buscou a configuracao, ou None."""
    from . import db
    row = conn.execute(select(db.telefones.c.ultimo_prov_ip)
                       .select_from(db.telefones.join(db.criancas, db.telefones.c.crianca_id == db.criancas.c.id))
                       .where(and_(db.criancas.c.familia_id == familia_id, db.telefones.c.ultimo_prov_ip.is_not(None)))
                       .order_by(db.telefones.c.ultimo_prov_em.desc().nulls_last(), db.telefones.c.id.desc())
                       .limit(1)).first()
    return row[0] if row else None


def sugerir(conn, familia_id, cfg, ip_navegador=None):
    """(ddd, origem, lugar). origem: 'familia' | 'celulares' | 'telefone_ip' | 'navegador_ip' | None.
    lugar: {'municipio', 'uf', 'raio_km'} quando veio de um IP, senao None."""
    d = ddd_da_familia(conn, familia_id)
    if d:
        return d, 'familia', None
    d = ddd_dos_celulares(conn, familia_id)
    if d:
        return d, 'celulares', None
    for origem, ip in (('telefone_ip', ip_do_telefone(conn, familia_id)), ('navegador_ip', ip_navegador)):
        if not ip:
            continue
        achado = por_ip(ip, cfg)
        if achado:
            return achado['ddd'], origem, {'municipio': achado['municipio'], 'uf': achado['uf'], 'raio_km': achado['raio_km']}
    return None, None, None


def descrever_origem(origem, lugar, apelido_crianca=None):
    """Frase curta para a familia: de onde veio a sugestao."""
    if origem == 'familia':
        return 'escolhido por você'
    if origem == 'celulares':
        return 'pelos celulares de casa'
    if origem in ('telefone_ip', 'navegador_ip') and lugar:
        onde = f"{lugar['municipio']}, {lugar['uf']}" if lugar.get('uf') else lugar['municipio']
        perto = 'perto de ' if (lugar.get('raio_km') or 0) > RAIO_CONFIAVEL_KM else 'em '
        quem = f'pelo telefone de {apelido_crianca}' if origem == 'telefone_ip' and apelido_crianca else (
            'pelo telefone da criança' if origem == 'telefone_ip' else 'pelo seu acesso agora')
        return f'{quem}, a casa parece estar {perto}{onde}'
    return ''


def parte_local(numero):
    """'1134567890' -> '34567890'."""
    return (numero or '')[2:]


def _grupos(local):
    return f'{local[:-4]} {local[-4:]}' if len(local) in (8, 9) else local


def formatar_discagem(numero, ddd_casa=None):
    """O que a crianca disca, agrupado para leitura: '3456 7890' (mesmo DDD) ou '19 3456 7890' (outro DDD).
    Sem DDD da casa definido, sempre com DDD."""
    if not numero or len(numero) not in (10, 11):
        return numero or ''
    ddd, local = numero[:2], numero[2:]
    return _grupos(local) if ddd_casa and ddd == ddd_casa else f'{ddd} {_grupos(local)}'
