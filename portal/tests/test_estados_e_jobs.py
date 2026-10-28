"""Maquina de estados, observador SIP, timeouts, reconciliacao, export, fila GDMS real com HTTP falso."""

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from conftest import post, cadastrar_e_entrar, criar_crianca, crianca_row, telefone_row, acoes, MAC, SN
from rede import estados
from rede.estados import TransicaoInvalida
from rede.servicos import sip, reconciliacao, gdms_fila, telefones
from rede.tempo import agora, agora_sp_texto


def _prep(client, app):
    cadastrar_e_entrar(client, app)
    cid = criar_crianca(client)
    post(client, f'/crianca/{cid}/telefone', acao='informar', mac=MAC, serial=SN)
    return cid, telefone_row(app, cid), crianca_row(app, cid)


def test_transicoes_invalidas(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        with pytest.raises(TransicaoInvalida):
            estados.transicionar(conn, t['id'], 'sip_registrado')
        with pytest.raises(TransicaoInvalida):
            estados.transicionar(conn, t['id'], 'gdms_ok')
    assert estados.pode('aguardando_boot', 'config_entregue')
    assert not estados.pode('registrado', 'config_entregue')
    assert estados.proximo_estado('ativo', 'desativar') == 'desativado'


def _registrar_contato(app, id_rede, ip='200.1.2.3', ua='Grandstream GRP2601', uri='sip:x'):
    with app.engine.begin() as c:
        c.execute(text("INSERT OR REPLACE INTO ps_contacts (id, uri, user_agent, via_addr, via_port, endpoint) "
                       "VALUES (:i, :uri, :ua, :ip, 5060, :e)"), {'i': id_rede + '^1', 'uri': uri, 'ua': ua, 'ip': ip, 'e': id_rede})


def test_ip_do_contato_prefere_uri_reescrita():
    # bancada 26/10/2026: contato reescrito com o IP publico, Via com o IP privado da casa
    assert sip.ip_do_contato('sip:7XX534@191.32.207.123:40134^3Btransport=TCP', '192.168.1.32') == '191.32.207.123'
    assert sip.ip_do_contato('sip:7XX534@191.32.207.123;transport=TCP', '192.168.1.32') == '191.32.207.123'
    assert sip.ip_do_contato('sip:1@[2001:db8::1]:5060', '10.0.0.1') == '2001:db8::1'
    assert sip.ip_do_contato('sip:x', '10.0.0.1') == '10.0.0.1'
    assert sip.ip_do_contato(None, '10.0.0.1') == '10.0.0.1'


def test_observador_nao_abre_caso_quando_so_o_via_e_privado(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        tok = conn.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t'), {'t': t['id']}).scalar()
    client.get(f'/p/{tok}/cfgc074ad010203.xml', environ_base={'REMOTE_ADDR': '191.32.207.123'})
    _registrar_contato(app, c['id_rede'], ip='192.168.1.32', uri=f"sip:{c['id_rede']}@191.32.207.123:40134^3Btransport=TCP")
    with app.engine.begin() as conn:
        sip.observar(conn, app.cfg)
        casos = [r[0] for r in conn.execute(text('SELECT tipo FROM casos')).all()]
        tel = conn.execute(text('SELECT estado, ultimo_sip_ip FROM telefones WHERE id=:i'), {'i': t['id']}).mappings().first()
    assert 'ip_divergente_sip' not in casos
    assert tel['estado'] == 'registrado' and tel['ultimo_sip_ip'] == '191.32.207.123'


def test_observador_registra_e_ativa(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        tok = conn.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t'), {'t': t['id']}).scalar()
    client.get(f'/p/{tok}/cfgc074ad010203.xml', environ_base={'REMOTE_ADDR': '200.1.2.3'})
    _registrar_contato(app, c['id_rede'])
    with app.engine.begin() as conn:
        r = sip.observar(conn, app.cfg)
    assert r['registrados'] == 1
    t2 = telefone_row(app, cid)
    assert t2['estado'] == 'registrado' and t2['ultimo_sip_ip'] == '200.1.2.3'
    # primeira chamada (100#) -> ativo
    with app.engine.begin() as conn:
        conn.execute(text("INSERT INTO call_logs (caller_ext, callee_ext, timestamp, status, duration_seconds) "
                          "VALUES (:c, '100', :t, 'ALLOWED', 5)"), {'c': c['id_rede'], 't': agora_sp_texto()})   # depois do registro
        sip.observar(conn, app.cfg)
    assert telefone_row(app, cid)['estado'] == 'ativo'
    assert 'jobs_rapidos_executados' in acoes(app)


def test_observador_ip_divergente_abre_caso(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        tok = conn.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t'), {'t': t['id']}).scalar()
    client.get(f'/p/{tok}/cfgc074ad010203.xml', environ_base={'REMOTE_ADDR': '200.1.2.3'})
    _registrar_contato(app, c['id_rede'], ip='177.9.9.9')
    with app.engine.begin() as conn:
        sip.observar(conn, app.cfg)
        casos = [r[0] for r in conn.execute(text('SELECT tipo FROM casos')).all()]
    assert 'ip_divergente_sip' in casos


def test_registro_fora_de_fluxo_rotaciona_senha(client, app):
    cid, t, c = _prep(client, app)   # aguardando_boot, sem config entregue
    _registrar_contato(app, c['id_rede'])
    with app.engine.begin() as conn:
        sip.observar(conn, app.cfg)
        casos = [r[0] for r in conn.execute(text('SELECT tipo FROM casos')).all()]
    assert 'credencial_vazada' in casos
    assert crianca_row(app, cid)['senha_sip'] != c['senha_sip']
    assert telefone_row(app, cid)['estado'] == 'aguardando_boot'


def test_timeouts_boot_e_registro(client, app):
    cid, t, c = _prep(client, app)
    post(client, f'/crianca/{cid}/telefone', acao='liguei')
    futuro = agora() + timedelta(minutes=app.cfg.PRAZO_SEM_BOOT_MIN + 1)
    with app.engine.begin() as conn:
        r = sip.observar(conn, app.cfg, ref=futuro)
    assert r['timeout_boot'] == 1 and telefone_row(app, cid)['estado'] == 'sem_boot'
    # entrega tardia ainda funciona (sem_boot -> config_entregue), depois timeout de registro
    with app.engine.begin() as conn:
        tok = conn.execute(text('SELECT token FROM prov_tokens WHERE telefone_id=:t'), {'t': t['id']}).scalar()
    assert client.get(f'/p/{tok}/cfgc074ad010203.xml').status_code == 200
    assert telefone_row(app, cid)['estado'] == 'config_entregue'
    with app.engine.begin() as conn:
        r = sip.observar(conn, app.cfg, ref=agora() + timedelta(minutes=app.cfg.PRAZO_SEM_REGISTRO_MIN + 1))
    assert r['timeout_registro'] == 1 and telefone_row(app, cid)['estado'] == 'sem_registro'
    with app.engine.begin() as conn:
        tipos = [r[0] for r in conn.execute(text('SELECT tipo FROM casos')).all()]
    assert 'sem_boot' in tipos and 'sem_registro' in tipos


def test_vinculo_expira(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        r = sip.observar(conn, app.cfg, ref=agora() + timedelta(days=app.cfg.VINCULO_EXPIRA_DIAS + 1))
    assert r['vinculos_expirados'] == 1
    assert telefone_row(app, cid) is None
    assert 'telefone_vinculo_expirado' in acoes(app, 'telefone', t['id'])


def test_reconciliacao_detecta_divergencias(client, app):
    cid, t, c = _prep(client, app)
    with app.engine.begin() as conn:
        r = reconciliacao.executar(conn, app.cfg, gdms_macs={t['mac'], 'C074AD00FFFF'})
    assert r['ramais_sem_linhas'] == 0 and r['tokens_divergentes'] == 0
    assert r['gdms_orfaos'] == 1 and r['gdms_faltando'] == 0
    with app.engine.begin() as conn:
        conn.execute(text('DELETE FROM ps_auths WHERE id=:i'), {'i': c['id_rede']})
        conn.execute(text("INSERT INTO ps_endpoints (id) VALUES ('777777')"))
        conn.execute(text('UPDATE prov_tokens SET ativo=0'))
        r = reconciliacao.executar(conn, app.cfg)
        tipos = [x[0] for x in conn.execute(text('SELECT tipo FROM casos')).all()]
    assert r['ramais_sem_linhas'] == 1 and r['linhas_sem_crianca'] == 1 and r['tokens_divergentes'] == 1
    assert {'ramal_inconsistente', 'ramal_orfao', 'token_divergente', 'gdms_orfao'} <= set(tipos)
    assert 'reconciliacao_executada' in acoes(app)


def test_export_auditoria_com_hash(client, app, tmp_path):
    cadastrar_e_entrar(client, app)
    import hashlib
    with app.engine.begin() as conn:
        r = reconciliacao.exportar_auditoria(conn, agora().strftime('%Y-%m-%d'), str(tmp_path / 'out'))
    assert r['linhas'] >= 5
    conteudo = open(r['arquivo'], 'rb').read()
    assert hashlib.sha256(conteudo).hexdigest() == r['sha256']
    assert open(r['arquivo'] + '.sha256').read().startswith(r['sha256'])
    assert 'auditoria_exportada' in acoes(app)


def test_fila_gdms_real_com_http_falso(app):
    """Modo real: HTTP falso responde ok para um MAC, conflito para outro, erro de rede para um terceiro."""
    from rede.config import Config
    from rede.servicos import contas, criancas
    cfg = Config(env={}, AMBIENTE='teste', DATABASE_URL=app.cfg.DATABASE_URL, GDMS_MODO='real', GDMS_ENVIO_MODO='manual',
                 GDMS_CLIENT_ID='cid', GDMS_CLIENT_SECRET='sec', GDMS_USERNAME='u', GDMS_PASSWORD='p',
                 GDMS_ORG_ID='1', GDMS_SITE_ID='2', GDMS_MAX_TENTATIVAS='2')
    respostas = {'C0:74:AD:00:00:01': {'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 1, 'failure': 0, 'errorDeviceList': []}},
                 'C0:74:AD:00:00:02': {'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 0, 'failure': 1,
                                       'errorDeviceList': [{'mac': 'C074AD000002', 'errorMsg': '30011'}]}}}

    def http_falso(metodo, url, corpo=None, headers=None, timeout=20):
        if url.endswith('/oapi/oauth/token'):
            return 200, json.dumps({'access_token': 'A', 'refresh_token': 'R'})
        if 'device/add' in url:
            mac = json.loads(corpo)[0]['mac']
            if mac == 'C0:74:AD:00:00:03':
                raise ConnectionError('rede caiu')
            return 200, json.dumps(respostas[mac])
        if 'device/list' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'result': [], 'total': 0}})
        return 200, '{}'

    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        tels = []
        for i, mac in enumerate(['C074AD000001', 'C074AD000002', 'C074AD000003']):
            cr = criancas.criar(conn, fid, f'kid{i}', cfg)
            t = telefones.informar(conn, cr, mac, 'SN00000000', '1.1.1.1', cfg, familia_id=fid)
            tels.append(t['id'])
        n = gdms_fila.processar(conn, cfg, http=http_falso)
        assert n == 3
        est = {tid: telefones.por_id(conn, tid)['estado'] for tid in tels}
        assert est[tels[0]] == 'gdms_cadastrado'          # ok, aguarda tarefa manual de RPS
        assert est[tels[1]] == 'erro_gdms_conflito'
        assert est[tels[2]] == 'dados_informados'         # retentativa agendada
        tarefas = conn.execute(text("SELECT tipo, telefone_id FROM tarefas WHERE estado='aberta'")).all()
        assert ('enviar_config_gdms', tels[0]) in tarefas
        glog = conn.execute(text('SELECT endpoint, ret_code, corpo_enviado FROM gdms_log ORDER BY id')).all()
        assert any(e == 'oauth/token' for e, _, _ in glog)
        assert all('"sec"' not in json.dumps(c) and '"A"' not in json.dumps(c) for _, _, c in glog if c)
        # segunda rodada no futuro: a retentativa estoura o maximo (2) e vira erro_dados + caso
        gdms_fila.processar(conn, cfg, http=http_falso, ref=agora() + timedelta(hours=5))
        assert telefones.por_id(conn, tels[2])['estado'] == 'erro_dados'
        tipos = [x[0] for x in conn.execute(text('SELECT tipo FROM casos')).all()]
        assert 'gdms_conflito' in tipos and 'gdms_falha_persistente' in tipos
        # operador conclui a tarefa manual -> config_enviada
        tid = [r for r in conn.execute(text("SELECT id FROM tarefas WHERE tipo='enviar_config_gdms'")).all()][0][0]
        with pytest.raises(ValueError):
            gdms_fila.concluir_tarefa(conn, tid, 'op@ong.org', '', cfg)
        gdms_fila.concluir_tarefa(conn, tid, 'op@ong.org', 'XML carregado no painel', cfg)
        assert telefones.por_id(conn, tels[0])['estado'] == 'aguardando_boot'
    a = acoes(app, 'telefone', tels[0])
    assert 'tarefa_operador_criada' in a and 'tarefa_operador_concluida' in a and 'telefone_config_enviada' in a
