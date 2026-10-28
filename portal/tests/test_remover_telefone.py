"""Remover telefone (28/10/2026): a familia aperta um botao; a fila manda a configuracao de fabrica ao
aparelho, pede o reset pela API e tira o MAC do GDMS. Operador so entra se o device/delete falhar."""
import json
from datetime import timedelta

from sqlalchemy import text

from rede import grandstream_xml
from rede.config import Config
from rede.servicos import contas, criancas, telefones, gdms_fila
from rede.tempo import agora


def test_pvalues_fabrica_desfazem_as_travas():
    pv = grandstream_xml.pvalues_fabrica('grp')
    travas = grandstream_xml.pvalues_travas('senha-admin-123', 'grp')
    assert set(travas) <= set(pv) and pv['P2'] == 'admin' and pv['P22373'] == '0' and pv['P1357'] == '0'
    assert pv['P271'] == '0' and pv['P34'] == '' and pv['P237'] == 'fm.grandstream.com/gs'
    assert 'P1365' in pv and 'P6767' not in pv and 'P6767' in grandstream_xml.pvalues_fabrica('ht')


def _cfg(app, **mais):
    base = dict(env={}, AMBIENTE='teste', DATABASE_URL=app.cfg.DATABASE_URL, GDMS_MODO='real', GDMS_ENVIO_MODO='api',
                GDMS_CLIENT_ID='cid', GDMS_CLIENT_SECRET='sec', GDMS_USERNAME='u', GDMS_PASSWORD='p',
                GDMS_ORG_ID='1', GDMS_SITE_ID='2', GDMS_MAX_TENTATIVAS='2')
    base.update(mais)
    return Config(**base)


def test_remover_zera_reseta_e_tira_do_gdms(app):
    cfg = _cfg(app)
    chamadas, xmls = [], []
    falhar_delete = {'vezes': 0}

    def http_falso(metodo, url, corpo=None, headers=None, timeout=20):
        if url.endswith('/oapi/oauth/token'):
            return 200, json.dumps({'access_token': 'A', 'refresh_token': 'R'})
        for nome in ('device/add', 'device/config/xml', 'task/add', 'device/delete', 'device/list'):
            if nome in url:
                chamadas.append(nome)
        if 'device/list' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'result': [], 'total': 0}})
        if 'device/add' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 1, 'failure': 0, 'errorDeviceList': []}})
        if 'device/config/xml' in url:
            xmls.append(corpo if isinstance(corpo, bytes) else str(corpo).encode())
            return 200, json.dumps({'retCode': 0, 'msg': ''})
        if 'device/delete' in url and falhar_delete['vezes'] > 0:
            falhar_delete['vezes'] -= 1
            return 200, json.dumps({'retCode': 50000, 'msg': 'erro temporario'})
        return 200, json.dumps({'retCode': 0, 'msg': ''})

    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000001', 'SN00000000', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=http_falso)
        assert telefones.por_id(conn, t['id'])['estado'] == 'aguardando_boot'
        chamadas.clear()
        # a familia remove: nada chama a API ainda, so enfileira
        telefones.desativar(conn, t['id'], 'familia', fid, motivo='familia_removeu', cfg=cfg)
        assert telefones.por_id(conn, t['id'])['estado'] == 'desativado' and chamadas == []
        assert conn.execute(text("SELECT count(*) FROM tarefas WHERE tipo='remover_gdms'")).scalar() == 0
        # passada 1: config de fabrica + reset; o delete fica para 3 minutos depois
        gdms_fila.processar(conn, cfg, http=http_falso)
        assert chamadas == ['device/config/xml', 'task/add']
        assert b'<P22373>0</P22373>' in xmls[-1] and b'<P271>0</P271>' in xmls[-1] and b'<P2>admin</P2>' in xmls[-1]
        fila = conn.execute(text("SELECT etapa, estado FROM gdms_fila ORDER BY id DESC LIMIT 1")).first()
        assert tuple(fila) == ('remover_gdms', 'pendente')
        assert conn.execute(text("SELECT xml_versao FROM telefones WHERE id=:i"), {'i': t['id']}).scalar() == 2
        # ainda nao venceu
        gdms_fila.processar(conn, cfg, http=http_falso)
        assert chamadas == ['device/config/xml', 'task/add']
        # passada 2 (3 min depois): delete falha uma vez e e reagendado; depois passa
        falhar_delete['vezes'] = 1
        gdms_fila.processar(conn, cfg, http=http_falso, ref=agora() + timedelta(minutes=4))
        assert chamadas[-1] == 'device/delete'
        assert conn.execute(text("SELECT estado FROM gdms_fila ORDER BY id DESC LIMIT 1")).scalar() == 'pendente'
        gdms_fila.processar(conn, cfg, http=http_falso, ref=agora() + timedelta(minutes=10))
        assert conn.execute(text("SELECT estado FROM gdms_fila ORDER BY id DESC LIMIT 1")).scalar() == 'ok'
        acoes = [r[0] for r in conn.execute(text('SELECT acao FROM audit_log')).all()]
        assert 'telefone_zerado_pedido' in acoes and 'gdms_removido' in acoes
        assert conn.execute(text("SELECT count(*) FROM tarefas WHERE tipo='remover_gdms'")).scalar() == 0


def test_delete_esgotado_vira_tarefa_de_operador(app):
    cfg = _cfg(app)

    def http_falso(metodo, url, corpo=None, headers=None, timeout=20):
        if url.endswith('/oapi/oauth/token'):
            return 200, json.dumps({'access_token': 'A', 'refresh_token': 'R'})
        if 'device/list' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'result': [], 'total': 0}})
        if 'device/add' in url:
            return 200, json.dumps({'retCode': 0, 'msg': '', 'data': {'total': 1, 'success': 1, 'failure': 0, 'errorDeviceList': []}})
        if 'device/delete' in url:
            raise ConnectionError('gdms fora')
        return 200, json.dumps({'retCode': 0, 'msg': ''})

    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000001', 'SN00000000', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg, http=http_falso)
        telefones.desativar(conn, t['id'], 'familia', fid, motivo='familia_removeu', cfg=cfg)
        gdms_fila.processar(conn, cfg, http=http_falso)
        gdms_fila.processar(conn, cfg, http=http_falso, ref=agora() + timedelta(minutes=4))
        gdms_fila.processar(conn, cfg, http=http_falso, ref=agora() + timedelta(hours=2))
        assert conn.execute(text("SELECT estado FROM gdms_fila ORDER BY id DESC LIMIT 1")).scalar() == 'erro'
        assert conn.execute(text("SELECT count(*) FROM tarefas WHERE tipo='remover_gdms' AND estado='aberta'")).scalar() == 1


def test_reativar_zera_as_marcas_da_ativacao_anterior(app):
    """Bancada B12 (28/10): o observador contava o prazo de boot a partir do "ja liguei" antigo e
    declarava sem_boot 20 s depois do Reativar."""
    from rede.servicos import sip
    cfg = _cfg(app, GDMS_MODO='simulado')
    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        t = telefones.informar(conn, cr, 'C074AD000001', 'SN00000000', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg)
        tel = telefones.por_id(conn, t['id'])
        telefones.familia_informou_ligado(conn, tel, fid)
        conn.execute(text("UPDATE telefones SET familia_ligou_em = :a WHERE id = :i"), {'a': agora() - timedelta(days=2), 'i': t['id']})
        telefones.desativar(conn, t['id'], 'familia', fid, motivo='familia_removeu', cfg=cfg)
        telefones.reativar(conn, telefones.por_id(conn, t['id']), 'familia', fid, cfg)
        gdms_fila.processar(conn, cfg)
        assert telefones.por_id(conn, t['id'])['estado'] == 'aguardando_boot'
        sip.observar(conn, cfg)
        assert telefones.por_id(conn, t['id'])['estado'] == 'aguardando_boot'   # e nao sem_boot


def test_reativado_nao_fica_ativo_por_ligacao_antiga(app):
    """B12 (28/10): o observador marcava o telefone reativado como 'ativo' por causa das ligacoes de antes."""
    from rede.servicos import sip, historico
    cfg = _cfg(app, GDMS_MODO='simulado')
    with app.engine.begin() as conn:
        fid = contas.criar_operador(conn, 'f@x.com', 'senha12345', 'F', 'familia')
        cr = criancas.criar(conn, fid, 'kid', cfg)
        conn.execute(text("INSERT INTO call_logs (caller_ext, callee_ext, timestamp, status, duration_seconds) VALUES (:c, '100', '2026-10-20 10:00:00', 'ALLOWED', 5)"), {'c': cr['id_rede']})
        assert historico.primeira_chamada_registrada(conn, cr['id_rede'])
        assert not historico.primeira_chamada_registrada(conn, cr['id_rede'], agora())
        t = telefones.informar(conn, cr, 'C074AD000001', 'SN00000000', '1.1.1.1', cfg, familia_id=fid)
        gdms_fila.processar(conn, cfg)
        from rede import estados
        estados.transicionar(conn, t['id'], 'config_entregue', 'telefone', cr['id_rede'])
        estados.transicionar(conn, t['id'], 'sip_registrado', 'telefone', cr['id_rede'])
        sip.observar(conn, cfg)
        assert telefones.por_id(conn, t['id'])['estado'] == 'registrado'
        conn.execute(text("INSERT INTO call_logs (caller_ext, callee_ext, timestamp, status, duration_seconds) VALUES (:c, '100', :t, 'ALLOWED', 5)"),
                     {'c': cr['id_rede'], 't': (agora() + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')})
        sip.observar(conn, cfg)
        assert telefones.por_id(conn, t['id'])['estado'] == 'ativo'
