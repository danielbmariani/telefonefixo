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
    # decisoes de 05/11: saem da pagina as frases sobre auditoria externa, copia so no servidor e fontes de terceiros
    for frase in ('auditoria de segurança feita por terceiros', 'Falta uma cópia em outro lugar', 'Google Fonts',
                  'ainda não é cifrado', 'O que falta', 'porta 5060'):
        assert frase not in html, frase
    assert 'a sinalização por TLS e a voz por SRTP' in html and 'porta 5061' in html
    # as fontes de terceiros e a copia de seguranca passam a constar da politica de privacidade
    pol = client.get('/privacidade').get_data(as_text=True)
    assert 'Google Fonts e jsDelivr' in pol and 'Cópias de segurança' in pol and 'versão 2026-11-a' in pol


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
    assert 'a não ser os celulares da própria família' in html
    # a pergunta sobre celular nao pode contradizer a aba Celulares (fase de teste)
    assert 'Só para os celulares que a própria família cadastrar' in final
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
