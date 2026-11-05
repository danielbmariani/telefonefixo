"""Pagina tecnica publica /por-dentro e os links para o codigo (doc 11, 05/11/2026)."""
import pathlib
import re

from conftest import cadastrar_e_entrar, criar_crianca

GH = 'https://github.com/danielbmariani/telefonefixo'


def test_por_dentro_e_publica_com_os_desenhos_e_as_secoes(client, app):
    r = client.get('/por-dentro')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count('<figure class="figura">') == 4
    for ancora in ('pecas', 'registro', 'ligacao', 'celular', 'dados', 'seguranca', 'codigo'):
        assert f'id="{ancora}"' in html and f'href="#{ancora}"' in html, ancora
    assert GH in html and 'São Paulo' in html and 'contato@telefonefixo.org' in html
    # o prazo do historico vem da configuracao, para nao divergir da retencao real
    assert f'{app.cfg.RETENCAO_CHAMADAS_DIAS} dias' in html
    # mesmas regras de texto do resto do site: sem travessao; nada de dinheiro para as familias
    assert '—' not in html and '–' not in html and 'R$' not in html


def test_arquivos_citados_na_pagina_existem_no_repositorio():
    fonte = pathlib.Path('rede/templates/por_dentro.html').read_text(encoding='utf-8')
    caminhos = re.findall(r'/(?:blob|tree)/main/([\w./-]+)"', fonte)
    assert len(caminhos) >= 6
    for c in caminhos:
        assert (pathlib.Path('..') / c).exists(), c


def test_pagina_inicial_e_rodape_levam_ao_codigo_e_a_pagina_tecnica(client, app):
    html = client.get('/').get_data(as_text=True)
    aberto = html[html.index('Sem fins lucrativos, com código aberto'):html.index('Perguntas comuns')]
    assert f'href="{GH}"' in aberto                       # link do codigo onde a pagina fala de codigo aberto
    final = html[html.index('Perguntas comuns'):html.index('<footer')]
    assert 'href="/por-dentro"' in final and f'href="{GH}"' in final   # secao no fim, para quem quer entender
    rodape = client.get('/entrar').get_data(as_text=True)
    rodape = rodape[rodape.index('<footer'):]
    assert 'href="/por-dentro"' in rodape and f'href="{GH}"' in rodape


def test_por_dentro_com_login_nao_vira_pagina_da_crianca(client, app):
    cadastrar_e_entrar(client, app)
    criar_crianca(client)
    r = client.get('/por-dentro')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'class="abas' not in html and 'data-copiar=' not in html
