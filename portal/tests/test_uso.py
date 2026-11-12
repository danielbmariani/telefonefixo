"""Aba Uso do painel: série por período (dia/semana/mês/ano) só com totais, CSV e abas em todas as páginas do operador."""

from datetime import timedelta

from sqlalchemy import insert, update

from rede import db
from rede.servicos import uso, contas
from rede.tempo import agora, em_sp
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def _operador(client, app):
    with app.engine.begin() as c:
        contas.criar_operador(c, 'op@ong.org', 'senha12345', 'Op')
    client.get('/sair')
    post(client, '/entrar', email='op@ong.org', senha='senha12345')


def _lig(app, de, para, dur, quando, status='ALLOWED', tronco=None):
    with app.engine.begin() as c:
        c.execute(insert(db.call_logs).values(caller_ext=de, callee_ext=para, status=status, duration_seconds=dur, tronco=tronco,
                                              timestamp=em_sp(quando).strftime('%Y-%m-%d %H:%M:%S')))


def test_serie_por_mes_e_por_dia(client, app):
    cadastrar_e_entrar(client, app)
    a = crianca_row(app, criar_crianca(client, 'ana01'))
    b = crianca_row(app, criar_crianca(client, 'bia02'))
    hoje = agora()
    with app.engine.begin() as c:
        c.execute(insert(db.telefones).values(crianca_id=a['id'], mac='C074AD010203', serial='S1', modelo='grp', estado='ativo',
                                              admin_senha='x', informado_em=hoje - timedelta(days=45)))
        c.execute(insert(db.telefones).values(crianca_id=b['id'], mac='C074AD010204', serial='S2', modelo='grp', estado='ativo',
                                              admin_senha='x', informado_em=hoje))
        # um terceiro telefone removido ha 10 dias: contou "na rede" nos periodos antigos, nao no atual
        # (telefones antigos entram na mesma data da ligacao antiga, 45 dias, para cairem no mesmo mes)
        c.execute(insert(db.telefones).values(crianca_id=a['id'], mac='C074AD010205', serial='S3', modelo='grp', estado='desativado',
                                              admin_senha='x', informado_em=hoje - timedelta(days=45), desativado_em=hoje - timedelta(days=10)))
    meio_dia = em_sp(hoje).replace(hour=15, minute=0, second=0, microsecond=0)
    _lig(app, a['id_rede'], b['id_rede'], 120, meio_dia)                       # telefone com telefone, hoje
    _lig(app, a['id_rede'], '9' + a['id_rede'], 61, meio_dia, tronco='vono')   # telefone para celular, hoje: 2 min pela Vono
    _lig(app, '11987654321', b['id_rede'], 30, meio_dia - timedelta(days=45))  # celular para telefone, 45 dias atras
    _lig(app, a['id_rede'], b['id_rede'], 0, meio_dia, status='BLOCKED')
    with app.engine.begin() as c:
        d = uso.serie(c, 'mes', 3, hoje)
    at = d['atual']
    assert at['atual'] and at['ligacoes'] == 2 and at['minutos'] == 4 and at['nao_completadas'] == 1
    assert at['tipos']['crianca_crianca'] == {'ligacoes': 1, 'minutos': 2, 'segundos': 120, 'nao_completadas': 1}
    assert at['tipos']['crianca_celular']['minutos'] == 2
    assert at['ativos'] == 2 and at['telefones'] == 2 and at['familias'] == 1
    assert at['telefones_novos'] == 1 and at['familias_novas'] == 1
    assert at['pct_ativos'] == 100 and at['media_min'] == 1.5
    assert at['troncos'] == {'vono': 2, 'nvoip': 0}
    # ha 45 dias: 1 ligacao do celular; dois telefones na rede (o removido ainda estava)
    antigo = next(l for l in d['periodos'] if l['tipos']['celular_crianca']['ligacoes'] == 1)
    assert antigo['ligacoes'] == 1 and antigo['ativos'] == 1 and antigo['telefones'] == 2
    assert antigo['troncos'] == {'vono': 0, 'nvoip': 1}   # sem tronco gravado conta como Nvoip
    assert d['horas'][15] == 3 and sum(v for _, v in d['dias_semana']) == 3
    assert dict(d['duracoes'])['até 1 min'] == 1 and dict(d['duracoes'])['1 a 3 min'] == 2
    assert sum(l['ligacoes'] for l in d['periodos']) == 3
    with app.engine.begin() as c:
        dd = uso.serie(c, 'dia', 7, hoje)
    assert len(dd['periodos']) == 7 and dd['atual']['ligacoes'] == 2 and dd['anterior']['ligacoes'] == 0
    assert dd['atual']['telefones'] == 2
    # dias ja resumidos pela retencao entram como total sem tipo
    with app.engine.begin() as c:
        c.execute(insert(db.chamadas_resumo).values(dia=em_sp(hoje - timedelta(days=2)).strftime('%Y-%m-%d'), chamadas=5, segundos=600, bloqueadas=1))
        dd = uso.serie(c, 'dia', 7, hoje)
    l = dd['periodos'][-3]
    assert l['antigas'] == 4 and l['ligacoes'] == 4 and l['minutos'] == 10 and l['nao_completadas'] == 1


def test_pagina_uso_csv_e_abas(client, app):
    cadastrar_e_entrar(client, app)
    criar_crianca(client, 'ana01')
    _operador(client, app)
    html = client.get('/ong/uso').get_data(as_text=True)
    assert 'Uso da rede' in html and 'Por semana' in html and 'Telefone com telefone' in html
    assert 'ana01' not in html
    r = client.get('/ong/uso?g=dia&n=5')
    assert r.status_code == 200 and r.get_data(as_text=True).count('(até agora)') == 1
    assert client.get('/ong/uso?g=xyz&n=-3').status_code == 200
    r = client.get('/ong/uso.csv?g=mes&n=2')
    assert r.status_code == 200 and r.mimetype == 'text/csv'
    linhas = r.get_data(as_text=True).strip().split('\n')
    assert len(linhas) == 3 and linhas[0].startswith('periodo;inicio;fim;familias_novas') and linhas[0].endswith(';min_celular_vono;min_celular_nvoip') and linhas[-1].endswith(';0;0;0;0;0')
    # as abas do operador aparecem em todas as paginas, com a atual marcada
    for url, aba in [('/ong/', 'Painel'), ('/ong/uso', 'Uso'), ('/ong/casos', 'Casos'), ('/ong/tarefas', 'Tarefas'),
                     ('/ong/telefones', 'Telefones'), ('/ong/auditoria', 'Auditoria')]:
        html = client.get(url).get_data(as_text=True)
        assert html.count('<nav class="abas') == 1, url
        for nome in ('Painel', 'Uso', 'Casos', 'Tarefas', 'Telefones', 'Auditoria'):
            assert f'<span class="rotulo">{nome}</span>' in html, (url, nome)
        assert f'nav-link active" href="{url if url != "/ong/" else "/ong/"}"' in html, url
    # familia nao ve as abas do operador
    client.get('/sair'); post(client, '/entrar', email='mae@x.com', senha='senha12345')
    assert client.get('/ong/uso').status_code == 403
