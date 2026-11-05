"""O ID da crianca fica no alto de todas as paginas dela, com botao Copiar (doc 11, 05/11/2026)."""
from sqlalchemy import text

from rede import ids
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def test_id_com_copiar_no_alto_de_todas_as_paginas_da_crianca(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    c = crianca_row(app, cid)
    for pagina in ('contatos', 'contatos/pedir', 'turmas', 'horarios', 'historico', 'celulares', 'telefone'):
        r = client.get(f'/crianca/{cid}/{pagina}')
        assert r.status_code == 200, pagina
        html = r.get_data(as_text=True)
        # um botao so, que copia o numero sem espacos; o numero aparece formatado; tudo antes das abas
        assert html.count(f'data-copiar="{c["id_rede"]}"') == 1, pagina
        assert f'aria-label="Copiar o ID de {c["apelido"]}"' in html, pagina
        assert ids.formatar_id(c['id_rede']) in html, pagina
        assert html.index('data-copiar=') < html.index('class="abas'), pagina


def test_lista_de_criancas_tem_copiar_em_cada_uma(client, app):
    cadastrar_e_entrar(client, app)
    a, b = crianca_row(app, criar_crianca(client, 'ana')), crianca_row(app, criar_crianca(client, 'beto'))
    r = client.get('/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for c in (a, b):
        assert html.count(f'data-copiar="{c["id_rede"]}"') == 1
        assert f'aria-label="Copiar o ID de {c["apelido"]}"' in html


def test_pagina_sem_crianca_nao_tem_faixa_do_id(client, app):
    cadastrar_e_entrar(client, app)
    criar_crianca(client)
    assert 'data-copiar=' not in client.get('/excluir-conta').get_data(as_text=True)


def test_codigo_da_turma_tem_copiar(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    r = post(client, f'/crianca/{cid}/turmas', acao='criar', nome='4o ano B')
    assert r.status_code == 302, r.data
    with app.engine.begin() as conn:
        tid, codigo = conn.execute(text('SELECT id, codigo FROM turmas')).one()
    html = client.get(f'/crianca/{cid}/turma/{tid}').get_data(as_text=True)
    assert f'data-copiar="{codigo}"' in html
    assert 'data-copiado="Código copiado"' in html


def test_campo_do_id_do_amigo_aceita_mensagem_colada(client, app):
    # o tratamento e no navegador (base.html); aqui so garante que o campo esta marcado para ele
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    assert 'data-colar-id' in client.get(f'/crianca/{cid}/contatos/pedir').get_data(as_text=True)


def test_celulares_e_aba_da_crianca_e_cabecalho_fica_so_com_sair(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana')
    r = client.get('/celulares')                      # endereco antigo leva para a aba
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/crianca/{cid}/celulares')
    html = client.get(f'/crianca/{cid}/celulares').get_data(as_text=True)
    cabecalho = html[html.index('<header'):html.index('</header>')]
    assert 'Sair' in cabecalho and 'Crianças' not in cabecalho and 'Celulares' not in cabecalho
    abas = html[html.index('class="abas'):html.index('</nav>', html.index('class="abas'))]
    assert f'/crianca/{cid}/celulares' in abas and 'nav-link active' in abas and abas.count('nav-item') == 6
    # com uma crianca so, nao aparece "Trocar de crianca"; a lista continua acessivel pelo rodape
    assert 'Trocar de criança' not in html and 'href="/criancas"' in html
    r = client.get('/criancas')
    assert r.status_code == 200 and 'ana' in r.get_data(as_text=True)
    criar_crianca(client, 'beto')
    assert 'Trocar de criança' in client.get(f'/crianca/{cid}/contatos').get_data(as_text=True)
