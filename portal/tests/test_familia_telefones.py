"""Telefones da familia: celulares de casa (B23: normalizacao, tela, 9+ID pelo tronco, entrada pelo tronco) e
outros telefones da lista (doc 20: DDD da casa, discagem pelo numero, recebe)."""

from datetime import datetime

import pytest
from sqlalchemy import text

from rede import db
from rede.servicos import familia_telefones as fam, chamadas, criancas as svc_cri, historico
from rede.servicos.contas import ErroUsuario
from rede.tempo import TZ_SP
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post


def test_normalizar_e_formatar():
    assert fam.normalizar('+55 (11) 98765-4321') == '11987654321'
    assert fam.normalizar('011987654321') == '11987654321'
    assert fam.normalizar('+5511987654321') == '11987654321'
    assert fam.normalizar('11 5108 3530') == '1151083530'
    assert fam.formatar('11987654321') == '(11) 98765-4321'
    assert fam.formatar('1151083530') == '(11) 5108-3530'
    for ruim in ('987654321', '10987654321', '11887654321', '', 'abc'):
        with pytest.raises(ErroUsuario):
            fam.normalizar(ruim)
    # Numero de outro pais: mensagem propria (o tronco so disca numero nacional)
    for estrangeiro in ('+351 912 345 678', '+1 212 555 0123', '00351912345678'):
        with pytest.raises(ErroUsuario, match='outro país'):
            fam.normalizar(estrangeiro)


def _ativar_telefone(app, crianca_id):
    from sqlalchemy import insert
    from rede import db
    from rede.tempo import agora
    with app.engine.begin() as c:
        c.execute(insert(db.telefones).values(crianca_id=crianca_id, mac='C074AD010203', serial='SN1', modelo='grp',
                                              estado='ativo', admin_senha='x', informado_em=agora()))


def test_tela_cadastra_e_remove(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    r = client.get(f'/crianca/{cid}/telefones')
    assert r.status_code == 200 and 'Nenhum celular cadastrado'.encode() in r.data
    r = post(client, f'/crianca/{cid}/telefones/novo-celular', numero='(11) 98765-4321', apelido='  Mãe  ', follow_redirects=True)
    assert '(11) 98765-4321'.encode() in r.data and 'Mãe'.encode() in r.data
    # repetido e limite
    r = post(client, f'/crianca/{cid}/telefones/novo-celular', numero='11987654321', apelido='x', follow_redirects=True)
    assert 'já está cadastrado'.encode() in r.data
    post(client, f'/crianca/{cid}/telefones/novo-celular', numero='11911111111', apelido='Pai')
    r = post(client, f'/crianca/{cid}/telefones/novo-celular', numero='11933333333', apelido='Tio', follow_redirects=True)
    assert 'No máximo 2'.encode() in r.data
    fid = crianca_row(app, cid)['familia_id']
    with app.engine.begin() as c:
        rows = fam.listar(c, fid)
        assert [(t['numero'], t['posicao']) for t in rows] == [('11987654321', 1), ('11911111111', 2)]
        primeiro = rows[0]['id']
    # trocar ordem pela tela
    r = post(client, f'/crianca/{cid}/telefones', acao='trocar', follow_redirects=True)
    assert 'Ordem trocada'.encode() in r.data
    with app.engine.begin() as c:
        assert [(t['numero'], t['posicao']) for t in fam.listar(c, fid)] == [('11911111111', 1), ('11987654321', 2)]
    # cartao mostra 9 e 8 com os apelidos
    r = client.get(f'/crianca/{cid}/cartao')
    cr = crianca_row(app, cid)
    assert f"Pai (celular)".encode() in r.data and f"9{cr['id_rede']}#".encode() in r.data and f"8{cr['id_rede']}#".encode() in r.data
    r = post(client, f'/crianca/{cid}/telefones', acao='remover', id=str(primeiro), follow_redirects=True)
    assert 'Número removido'.encode() in r.data
    with app.engine.begin() as c:
        rows = fam.listar(c, fid)
        assert len(rows) == 1 and rows[0]['posicao'] == 1          # ficou so o Pai, na posicao 1
        # readicionar reativa a mesma linha, na posicao livre (2)
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        rows = fam.listar(c, fid)
        assert [(t['apelido'], t['posicao']) for t in rows] == [('Pai', 1), ('Mãe', 2)]


def test_nove_mais_id_decide(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    outra = crianca_row(app, criar_crianca(client, 'bia02'))
    t = TZ_SP.localize(datetime(2026, 10, 27, 15, 0))
    with app.engine.begin() as c:
        # sem celular cadastrado
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], t) == ('BLOCK_PARENT', 'FAMILIA_NAO_CONFIGURADA')
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        # so o celular 1: 9 funciona, 8 ainda nao
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], t) == ('ALLOW', 'PJSIP/11987654321@nvoip;limite=1000;vono=0')
        assert chamadas.decidir(c, cr['id_rede'], '8' + cr['id_rede'], t) == ('BLOCK_PARENT', 'FAMILIA_NAO_CONFIGURADA')
        fam.adicionar(c, cr['familia_id'], '11911111111', 'Pai')
        assert chamadas.decidir(c, cr['id_rede'], '8' + cr['id_rede'], t) == ('ALLOW', 'PJSIP/11911111111@nvoip;limite=1000;vono=0')
        # 9 + ID de outra crianca (mesmo da mesma familia) nao vale
        assert chamadas.decidir(c, cr['id_rede'], '9' + outra['id_rede'], t)[0] == 'BLOCK_PERMISSION'
        # crianca desconhecida
        assert chamadas.decidir(c, '299999', '9299999', t)[0] == 'BLOCK_UNKNOWN'
        # rotulos no historico
        n = historico.nomes(c, ['9' + cr['id_rede'], '11987654321', cr['id_rede']])
        assert n['9' + cr['id_rede']] == 'Celular 1 da família'
        assert historico.nomes(c, ['8' + cr['id_rede']])['8' + cr['id_rede']] == 'Celular 2 da família'
        assert n['11987654321'] == 'Celular da família (11) 98765-4321'
        assert n[cr['id_rede']] == 'ana01'


def test_nove_mais_id_respeita_horario(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    post(client, f'/crianca/{cid}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_11 = TZ_SP.localize(datetime(2026, 10, 26, 11, 0))
    seg_15 = TZ_SP.localize(datetime(2026, 10, 26, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], seg_11)[0] == 'ALLOW'
        assert chamadas.decidir(c, cr['id_rede'], '9' + cr['id_rede'], seg_15)[0] == 'BLOCK_SCHEDULE_CALLER'


def test_entrada_pelo_tronco(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    cid2 = criar_crianca(client, 'bia02')
    cr2 = crianca_row(app, cid2)
    t = TZ_SP.localize(datetime(2026, 10, 27, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11987654321', 'Mãe')
        # numero desconhecido
        assert fam.decidir_entrada(c, '11900000000', t)[0] == 'BLOCK_UNKNOWN'
        assert fam.decidir_entrada(c, 'anonymous', t)[0] == 'BLOCK_UNKNOWN'
        # numero do chamador no display name (Nvoip) ou no P-Asserted-Identity; From user = nosso tronco
        assert fam.numero_do_identificador('15XXXXXXX', '11987654321') == '11987654321'
        assert fam.numero_do_identificador('15XXXXXXX', '', '"x" <sip:+5511987654321@op.br>;party=calling') == '11987654321'
        assert fam.numero_do_identificador('15XXXXXXX', 'Anonymous', '') == ''
        # conhecido, mas nenhuma crianca com telefone conectado
        assert fam.decidir_entrada(c, '+5511987654321', t)[0] == 'BLOCK_NO_PHONE'
        assert fam.decidir_entrada(c, '15XXXXXXX', t, '11987654321')[0] == 'BLOCK_NO_PHONE'
    _ativar_telefone(app, cid)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '+5511987654321', t)
        assert res == 'ALLOW' and d['ids'] == [cr['id_rede']] and d['dial'] == f"PJSIP/{cr['id_rede']}" and d['nome'] == 'Mãe'
        assert d['numero'] == '11987654321'
        # identificador sem o nono digito tambem casa
        assert fam.decidir_entrada(c, '1187654321', t)[0] == 'ALLOW'
    _ativar_telefone(app, cid2)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '11987654321', t)
        assert res == 'ALLOW' and sorted(d['ids']) == sorted([cr['id_rede'], cr2['id_rede']])
        assert '&' in d['dial']
    # fora do horario de todas -> BLOCK_SCHEDULE_DEST
    post(client, f'/crianca/{cid}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    post(client, f'/crianca/{cid2}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_15 = TZ_SP.localize(datetime(2026, 10, 26, 15, 0))
    with app.engine.begin() as c:
        assert fam.decidir_entrada(c, '11987654321', seg_15)[0] == 'BLOCK_SCHEDULE_DEST'
    # removido -> desconhecido
    with app.engine.begin() as c:
        tid = fam.listar(c, cr['familia_id'])[0]['id']
        fam.remover(c, cr['familia_id'], tid)
        assert fam.decidir_entrada(c, '11987654321', t)[0] == 'BLOCK_UNKNOWN'


def test_pagina_mostra_numero_que_aparece_no_celular(client, app):
    """B30: a criança liga pela Vono e o celular mostra outro número; a página pede para salvar os dois
    (aviso de 12/11/2026, depois de uma mãe ter ligações silenciadas por ter salvo só um)."""
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    app.cfg.TRONCO_NUMERO, app.cfg.TRONCO_NUMERO_SAIDA = '1151083530', '1154441774'
    # Antes de cadastrar qualquer celular o aviso ja aparece
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'Salve estes dois números nos contatos do celular' in html
    aviso = html.split('id="aviso-dois-numeros"')[1].split('</div>')[0]
    assert '(11) 5444-1774' in aviso and '(11) 5108-3530' in aviso and 'pode aparecer qualquer um dos dois' in aviso
    post(client, f'/crianca/{cid}/telefones/novo-celular', numero='11987654321', apelido='Mãe')
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'Salve estes dois números' in html and '<span class="mono discar-caixa">(11) 5108-3530</span>' in html
    # Com um numero so (depois da portabilidade), o aviso fala de um numero
    app.cfg.TRONCO_NUMERO_SAIDA = '1151083530'
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'Salve este número nos contatos do celular' in html and 'dois números' not in html
    assert html.count('(11) 5108-3530') >= 2
    # Sem tronco configurado, nenhum aviso
    app.cfg.TRONCO_NUMERO = app.cfg.TRONCO_NUMERO_SAIDA = ''
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'aviso-dois-numeros' not in html


# --- Outros telefones da lista (doc 20) ---

def test_normalizar_com_ddd_da_casa_e_servicos():
    assert fam.normalizar('3456 7890', '11') == '1134567890'
    assert fam.normalizar('98765-4321', '19') == '19987654321'
    assert fam.normalizar('(21) 3456-7890', '11') == '2134567890'      # com DDD, o da casa nao entra
    assert fam.normalizar('0 21 3456 7890', '11') == '2134567890'
    assert fam.normalizar('+55 21 3456-7890') == '2134567890'
    with pytest.raises(ErroUsuario, match='com ou sem DDD'):
        fam.normalizar('3456 789', '11')
    with pytest.raises(ErroUsuario, match='com DDD'):
        fam.normalizar('3456 7890')                                       # sem DDD da casa, so com DDD
    with pytest.raises(ErroUsuario, match='começa com 2, 3, 4 ou 5'):
        fam.normalizar('11 1234 5678')
    for servico in ('0800 123 4567', '0300 313 1234', '0303 123 4567', '0500 123 4567', '0900 123 4567', '4004 1234', '11 4004 1234', '800 123 4567'):
        with pytest.raises(ErroUsuario, match='número de serviço'):
            fam.normalizar(servico, '11')
    with pytest.raises(ErroUsuario, match='DDD inválido'):
        fam.normalizar('20 3456 7890')


def test_outros_telefones_cadastro_limite_e_recebe(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    fid = crianca_row(app, cid)['familia_id']
    with app.engine.begin() as c:
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        assert fam.adicionar(c, fid, '3456 7890', 'Vó Lúcia', atalho=False, ddd_casa='11') == '1134567890'
        assert fam.adicionar(c, fid, '19 3333 4444', 'Casa do Théo', atalho=False) == '1933334444'
        assert fam.adicionar(c, fid, '2222 3333', 'Padaria', atalho=False, recebe=False, ddd_casa='11') == '1122223333'
        atalhos, outros = fam.listar_atalhos(c, fid), fam.listar_outros(c, fid)
        assert [t['numero'] for t in atalhos] == ['11987654321'] and atalhos[0]['recebe'] is True
        assert [(t['apelido'], t['numero'], t['posicao'], t['recebe']) for t in outros] == [
            ('Vó Lúcia', '1134567890', None, True), ('Casa do Théo', '1933334444', None, True), ('Padaria', '1122223333', None, False)]
        # os outros nao ocupam as posicoes dos atalhos: ainda cabe o celular 2
        fam.adicionar(c, fid, '11911111111', 'Pai')
        assert [t['posicao'] for t in fam.listar_atalhos(c, fid)] == [1, 2]
        # repetido (em qualquer dos dois tipos) e limite dos outros
        with pytest.raises(ErroUsuario, match='já está cadastrado como Vó Lúcia'):
            fam.adicionar(c, fid, '11 3456 7890', 'x', atalho=False)
        with pytest.raises(ErroUsuario, match='já está cadastrado'):
            fam.adicionar(c, fid, '11987654321', 'x', atalho=False)
        with pytest.raises(ErroUsuario, match='cheia'):
            fam.adicionar(c, fid, '11 5555 6666', 'x', atalho=False, max_outros=3)
        with pytest.raises(ErroUsuario, match='desligado'):
            fam.adicionar(c, fid, '11 5555 6666', 'x', atalho=False, max_outros=0)
        # recebe liga e desliga; remover e readicionar como outro mantem posicao None
        padaria = next(t for t in outros if t['apelido'] == 'Padaria')
        assert fam.mudar_recebe(c, fid, padaria['id'], True)
        assert next(t for t in fam.listar_outros(c, fid) if t['id'] == padaria['id'])['recebe'] is True
        assert fam.remover(c, fid, padaria['id'])
        assert fam.apelido_do_numero(c, fid, '1122223333') == 'Padaria'     # removido: ainda rotula o historico
        fam.adicionar(c, fid, '1122223333', 'Padaria da esquina', atalho=False, recebe=False)
        de_novo = next(t for t in fam.listar_outros(c, fid) if t['numero'] == '1122223333')
        assert de_novo['id'] == padaria['id'] and de_novo['posicao'] is None and de_novo['recebe'] is False
        assert fam.apelido_do_numero(c, fid, '1122223333') == 'Padaria da esquina'
        assert fam.apelido_do_numero(c, fid, '1199999999') is None
    # a aba Telefones mostra os celulares de casa e os outros, com o que discar (sem DDD da casa: sempre com DDD)
    html = client.get(f'/crianca/{cid}/telefones').get_data(as_text=True)
    assert 'Mãe' in html and 'Pai' in html and 'Vó Lúcia' in html and 'Casa do Théo' in html
    assert 'discar <span class="mono">3456 7890#</span>' in html and 'discar <span class="mono">19 3333 4444#</span>' in html
    # meus-dados traz tudo, com recebe
    dados = client.get('/meus-dados.json').get_json()
    assert len(dados['celulares']) == 5 and dados['celulares'][0]['recebe'] is True and dados['ddd_da_casa'] is None


def test_casar_discado_pelo_fim_do_numero(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    fid = crianca_row(app, cid)['familia_id']
    with app.engine.begin() as c:
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        fam.adicionar(c, fid, '11 3456 7890', 'Vó', atalho=False)
        fam.adicionar(c, fid, '19 3456 7890', 'Casa do Théo', atalho=False)
        fam.adicionar(c, fid, '21 2222 3333', 'Tio', atalho=False)
        # numero inteiro
        assert fam.casar_discado(c, fid, 'externo', '2122223333') == ('2122223333', None)
        assert fam.casar_discado(c, fid, 'externo', '11987654321') == ('11987654321', None)   # celular de casa pelo numero
        assert fam.casar_discado(c, fid, 'externo', '2199999999') == (None, 'EXTERNO_FORA_DA_LISTA')
        # so o numero: uma entrada, e ela (mesmo sem DDD da casa, mesmo sendo de outro DDD)
        assert fam.casar_discado(c, fid, 'externo_local', '22223333') == ('2122223333', None)
        assert fam.casar_discado(c, fid, 'externo_local', '987654321', '11') == ('11987654321', None)
        # duas entradas com o mesmo fim: o DDD da casa decide; sem ele, pede o DDD
        assert fam.casar_discado(c, fid, 'externo_local', '34567890', '11') == ('1134567890', None)
        assert fam.casar_discado(c, fid, 'externo_local', '34567890', '19') == ('1934567890', None)
        assert fam.casar_discado(c, fid, 'externo_local', '34567890', None) == (None, 'EXTERNO_AMBIGUO')
        assert fam.casar_discado(c, fid, 'externo_local', '34567890', '21') == (None, 'EXTERNO_AMBIGUO')
        assert fam.casar_discado(c, fid, 'externo_local', '99999999') == (None, 'EXTERNO_FORA_DA_LISTA')


def test_decidir_telefone_da_lista(client, app, monkeypatch):
    from rede.servicos import custos
    from rede.servicos.contas import definir_ddd
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    t = TZ_SP.localize(datetime(2026, 11, 13, 15, 0))
    with app.engine.begin() as c:
        # lista vazia: fora da lista, com som proprio
        assert chamadas.decidir(c, cr['id_rede'], '34567890', t) == ('BLOCK_EXTERNO', 'EXTERNO_FORA_DA_LISTA')
        fam.adicionar(c, cr['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        fam.adicionar(c, cr['familia_id'], '19 3456 7890', 'Théo', atalho=False)
        fam.adicionar(c, cr['familia_id'], '21 98765 4321', 'Tia', atalho=False)
        # DDD + numero, com e sem 0 e 55: o Dial vai com o numero normalizado e dest= para o historico
        esperado = ('ALLOW', 'PJSIP/21987654321@nvoip;limite=1000;vono=0;dest=21987654321')
        for discado in ('21987654321', '021987654321', '5521987654321'):
            assert chamadas.decidir(c, cr['id_rede'], discado, t) == esperado, discado
        # so o numero: 9 digitos unico; 8 digitos repetido em 11 e 19 sem DDD da casa -> ambiguo
        assert chamadas.decidir(c, cr['id_rede'], '987654321', t) == esperado
        assert chamadas.decidir(c, cr['id_rede'], '34567890', t) == ('BLOCK_AMBIGUO', 'EXTERNO_AMBIGUO')
        definir_ddd(c, cr['familia_id'], '19')
        assert chamadas.decidir(c, cr['id_rede'], '34567890', t)[1].endswith(';dest=1934567890')
        # fora da lista e crianca desconhecida
        assert chamadas.decidir(c, cr['id_rede'], '1159998888', t) == ('BLOCK_EXTERNO', 'EXTERNO_FORA_DA_LISTA')
        assert chamadas.decidir(c, cr['id_rede'], '1199998888', t) == ('BLOCK_UNKNOWN', 'UNKNOWN_DEST')   # fixo nao comeca com 9
        assert chamadas.decidir(c, '299999', '1134567890', t) == ('BLOCK_UNKNOWN', 'CALLER_NOT_ACTIVATED')
        # bloqueios ficam no historico com o que foi discado
        motivos = [r[0] for r in c.execute(text("SELECT block_reason FROM call_logs WHERE status='BLOCKED' ORDER BY id")).all()]
        assert motivos == ['EXTERNO_FORA_DA_LISTA', 'EXTERNO_AMBIGUO', 'EXTERNO_FORA_DA_LISTA', 'UNKNOWN_DEST', 'CALLER_NOT_ACTIVATED']
        # recurso desligado (fora do Flask, como no AGI, a configuracao vem do ambiente)
        monkeypatch.setenv('REDE_MAX_OUTROS', '0')
        assert chamadas.decidir(c, cr['id_rede'], '1934567890', t) == ('BLOCK_UNKNOWN', 'EXTERNO_DESLIGADO')
        monkeypatch.delenv('REDE_MAX_OUTROS')
        # a ligacao gravada pelo log_call (callee = numero normalizado) conta no teto e no uso da crianca
        c.execute(db.call_logs.insert().values(caller_ext=cr['id_rede'], callee_ext='1934567890', timestamp=t.strftime('%Y-%m-%d %H:%M:%S'),
                                               status='ALLOWED', duration_seconds=125, tronco='vono'))
        assert custos.uso_crianca_mes(c, cr['id_rede'], app.cfg, t)['usados'] == 3
        assert custos.gasto_crianca_mes(c, cr['id_rede'], app.cfg, t) == round(3 * app.cfg.TARIFA_SAIDA_MIN, 2)
        assert custos.minutos_vono_mes(c, t) == 3
        # historico: com a familia, o numero ganha o nome da lista
        n = historico.nomes(c, ['1934567890', '2199999999'], cr['familia_id'])
        assert n['1934567890'] == 'Théo (19) 3456-7890' and n['2199999999'] == 'Celular da família (21) 9999-9999'
        assert historico.nomes(c, ['1934567890'])['1934567890'] == 'Celular da família (19) 3456-7890'


def test_horario_e_teto_valem_para_telefone_da_lista(client, app, monkeypatch):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    post(client, f'/crianca/{cid}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_11 = TZ_SP.localize(datetime(2026, 11, 9, 11, 0))
    seg_15 = TZ_SP.localize(datetime(2026, 11, 9, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        assert chamadas.decidir(c, cr['id_rede'], '34567890', seg_11)[0] == 'ALLOW'
        assert chamadas.decidir(c, cr['id_rede'], '34567890', seg_15)[0] == 'BLOCK_SCHEDULE_CALLER'
        monkeypatch.setenv('REDE_TETO_CRIANCA_MES', '0.01')
        assert chamadas.decidir(c, cr['id_rede'], '34567890', seg_11)[0] == 'BLOCK_TETO'


def test_entrada_so_de_numero_com_recebe(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    cr = crianca_row(app, cid)
    _ativar_telefone(app, cid)
    t = TZ_SP.localize(datetime(2026, 11, 13, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        fam.adicionar(c, cr['familia_id'], '11 2222 3333', 'Padaria', atalho=False, recebe=False)
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'ALLOW' and d['nome'] == 'Vó' and d['ids'] == [cr['id_rede']]
        assert fam.decidir_entrada(c, '1122223333', t)[0] == 'BLOCK_UNKNOWN'
        padaria = next(x for x in fam.listar_outros(c, cr['familia_id']) if x['apelido'] == 'Padaria')
        fam.mudar_recebe(c, cr['familia_id'], padaria['id'], True)
        assert fam.decidir_entrada(c, '1122223333', t)[0] == 'ALLOW'


def test_migrar_cria_recebe_com_default_para_linhas_antigas(client, app):
    from sqlalchemy import inspect
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client, 'ana01')
    fid = crianca_row(app, cid)['familia_id']
    with app.engine.begin() as c:
        fam.adicionar(c, fid, '11987654321', 'Mãe')
        c.execute(text('ALTER TABLE familia_telefones DROP COLUMN recebe'))
    faltam = db.colunas_faltando(app.engine)
    assert [(t_, col) for t_, col, _ in faltam] == [('familia_telefones', 'recebe')]
    assert 'DEFAULT' in faltam[0][2] and 'NOT NULL' in faltam[0][2]
    assert db.migrar(app.engine) == [('familia_telefones', 'recebe')]
    assert 'recebe' in {col['name'] for col in inspect(app.engine).get_columns('familia_telefones')}
    with app.engine.begin() as c:
        assert fam.listar(c, fid)[0]['recebe'] is True
        assert fam.familia_por_numero(c, '11987654321') is not None


def test_entrada_mesmo_numero_em_duas_familias_vira_menu(client, app):
    """Doc 20, 3.3: a vo com netos em duas casas. Uma familia so: toca direto. Duas: a central pergunta."""
    cadastrar_e_entrar(client, app)
    cid_a = criar_crianca(client, 'ana01')
    cr_a = crianca_row(app, cid_a)
    _ativar_telefone(app, cid_a)
    client.get('/sair')
    cadastrar_e_entrar(client, app, email='outra@x.com', nome='Outra')
    cid_b = criar_crianca(client, 'bia02')
    cr_b = crianca_row(app, cid_b)
    t = TZ_SP.localize(datetime(2026, 11, 13, 15, 0))
    with app.engine.begin() as c:
        fam.adicionar(c, cr_a['familia_id'], '11 3456 7890', 'Vó Lúcia', atalho=False)
        fam.adicionar(c, cr_b['familia_id'], '11 3456 7890', 'Vó', atalho=False)
        assert [r['familia_id'] for r in fam.familias_por_numero(c, '1134567890')] == [cr_a['familia_id'], cr_b['familia_id']]
        # a segunda familia ainda nao tem telefone conectado: toca direto na primeira, sem menu
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'ALLOW' and d['ids'] == [cr_a['id_rede']] and d['nome'] == 'Vó Lúcia'
    _ativar_telefone(app, cid_b)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'MENU' and d['numero'] == '1134567890'
        assert [(o['id_rede'], o['apelido'], o['nome']) for o in d['opcoes']] == [
            (cr_a['id_rede'], 'ana01', 'Vó Lúcia'), (cr_b['id_rede'], 'bia02', 'Vó')]
        assert all(o['limite_s'] > 0 for o in d['opcoes'])
        # sem 'recebe' numa das familias, volta a ser uma so
        tel_b = next(x for x in fam.listar_outros(c, cr_b['familia_id']))
        fam.mudar_recebe(c, cr_b['familia_id'], tel_b['id'], False)
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'ALLOW' and d['ids'] == [cr_a['id_rede']]
        fam.mudar_recebe(c, cr_b['familia_id'], tel_b['id'], True)
    # fora do horario em uma das familias: so a outra entra; nas duas: bloqueio por horario
    post(client, f'/crianca/{cid_b}/horarios', pattern_count='1', days_0=['0'], start_h_0='09', start_m_0='00', end_h_0='12', end_m_0='00')
    seg_15 = TZ_SP.localize(datetime(2026, 11, 9, 15, 0))
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '1134567890', seg_15)
        assert res == 'ALLOW' and d['ids'] == [cr_a['id_rede']]
        # duas criancas na mesma familia + outra familia: tres opcoes, na ordem das familias
    client.get('/sair')
    post(client, '/entrar', email='mae@x.com', senha='senha12345')
    cid_a2 = criar_crianca(client, 'caio03')
    _ativar_telefone(app, cid_a2)
    with app.engine.begin() as c:
        res, d = fam.decidir_entrada(c, '1134567890', t)
        assert res == 'MENU' and [o['apelido'] for o in d['opcoes']] == ['ana01', 'caio03', 'bia02']


def test_dialplan_e_frases_do_menu_batem():
    """As frases que o dialplan toca existem em voz.FRASES (senao o Asterisk toca silencio)."""
    import re
    from rede import voz
    conf = open(__file__.rsplit('/tests/', 1)[0] + '/deploy/asterisk/extensions.conf', encoding='utf-8').read()
    usadas = {u for u in re.findall(r'rede/frases/([a-z0-9-]+)', conf) if not u.endswith('-')}   # 'tecle-${MENU_I}' fica de fora
    assert {'para-falar-com', 'nao-deu-certo', 'nao-esta-na-lista-de-casa', 'disque-com-ddd'} <= usadas
    assert usadas <= set(voz.FRASES)
    for i in range(1, 10):
        assert f'tecle-{i}' in voz.FRASES
    assert 'ENTRADA_OPCOES' in conf and 'Read(MENU_ESCOLHA' in conf and '"${ENTRADA_RESULT}" = "MENU"' in conf
