"""
gdms_fila.py — E4 e E5: fila de cadastro no GDMS com retentativas, e envio da
configuracao inicial ao aparelho pelo proprio GDMS (device/config/xml).

Modos (cfg.GDMS_MODO):
  desligado  nao faz nada (telefone fica em dados_informados; usar so em dev)
  simulado   nao chama a API; marca gdms_ok e config_enviada (para testar o resto do fluxo com softphone)
  real       chama a API via gdms_client

E5 (cfg.GDMS_ENVIO_MODO):
  api     depois do device/add, POST device/config/xml com o XML de telefones.gerar_xml_gdms.
          Sem operador. Se a chamada falhar, a fila re-tenta so o envio (etapa 'config').
  manual  abre tarefa no painel: operador carrega o XML em Dispositivo VoIP > Definir parametros.
"""

from datetime import timedelta

from sqlalchemy import select, insert, update, and_

from .. import db, auditoria, estados, gdms_client
from ..tempo import agora, utc
from . import telefones as svc_tel, criancas as svc_cri

BACKOFF_MIN = [1, 5, 30, 120, 360, 720]

# Bancada 2026-10-23: device/add devolve retCode 0 mesmo em falha; o detalhe esta em
# data.errorDeviceList[].errorMsg. Mapeamento em gdms_client.ERROS_DEVICE_ADD:
#   30007 ja_na_organizacao  -> tratar como ok (idempotente)
#   30011 em_outra_organizacao -> conflito (outra org; de outra CONTA ainda a confirmar, B13)
#   50025 site_invalido -> erro de configuracao nossa (nao enviar siteId)
# Codigo para serial errado: A CONFIRMAR (B14 com o GRP2601 real).
STATUS_PARA_RESULTADO = {  # device/add
    'ok': 'ok', 'ja_na_organizacao': 'ok', 'em_outra_organizacao': 'conflito',
    'serial_errado': 'dados_invalidos', 'mac_invalido': 'dados_invalidos', 'modelo_nao_suportado': 'dados_invalidos',
    'site_invalido': 'temporario', 'erro_desconhecido': 'temporario', 'temporario': 'temporario',
}


def enfileirar(conn, telefone_id):
    conn.execute(update(db.gdms_fila).where(and_(db.gdms_fila.c.telefone_id == telefone_id,
                                                 db.gdms_fila.c.estado == 'pendente')).values(estado='cancelada', atualizado_em=agora()))
    conn.execute(insert(db.gdms_fila).values(telefone_id=telefone_id, estado='pendente', tentativas=0,
                                             proxima_em=agora(), criado_em=agora()))


ESTADOS_REENVIO = ('gdms_cadastrado', 'aguardando_boot', 'config_entregue', 'registrado', 'ativo')


def atualizar_teclas(conn, crianca_id):
    """Amizade mudou: reenvia so as teclas de discagem rapida ao telefone da crianca, pelo GDMS
    (aplica na hora, sem reboot; o cfg completo e rebuscado no recheck diario). Sem telefone: nada."""
    tel = svc_tel.atual_da_crianca(conn, crianca_id)
    if not tel or tel['estado'] not in ESTADOS_REENVIO:
        return False
    conn.execute(update(db.gdms_fila).where(and_(db.gdms_fila.c.telefone_id == tel['id'], db.gdms_fila.c.estado == 'pendente',
                                                 db.gdms_fila.c.etapa == 'teclas')).values(estado='cancelada', atualizado_em=agora()))
    conn.execute(insert(db.gdms_fila).values(telefone_id=tel['id'], estado='pendente', etapa='teclas', tentativas=0,
                                             proxima_em=agora(), criado_em=agora()))
    return True


def reenviar_config(conn, telefone_id):
    """Enfileira so o envio da configuracao (device/config/xml) para um telefone que ja esta no GDMS.
    Uso: mudou o conteudo do XML ponteiro (ex.: travas) e nao da para esperar o recheck do P193."""
    conn.execute(update(db.gdms_fila).where(and_(db.gdms_fila.c.telefone_id == telefone_id,
                                                 db.gdms_fila.c.estado == 'pendente')).values(estado='cancelada', atualizado_em=agora()))
    conn.execute(insert(db.gdms_fila).values(telefone_id=telefone_id, estado='pendente', etapa='config', tentativas=0,
                                             proxima_em=agora(), criado_em=agora()))


def cancelar(conn, telefone_id):
    conn.execute(update(db.gdms_fila).where(and_(db.gdms_fila.c.telefone_id == telefone_id,
                                                 db.gdms_fila.c.estado == 'pendente')).values(estado='cancelada', atualizado_em=agora()))


def pendentes(conn, ref=None):
    ref = ref or agora()
    return conn.execute(select(db.gdms_fila).where(and_(db.gdms_fila.c.estado == 'pendente',
                                                       db.gdms_fila.c.proxima_em <= ref))
                        .order_by(db.gdms_fila.c.id)).mappings().all()


def criar_cliente(cfg, conn, telefone_id=None, http=None):
    def registrar(linha):
        conn.execute(insert(db.gdms_log).values(
            ts=agora(), request_id=auditoria.request_id(), telefone_id=telefone_id,
            endpoint=linha['endpoint'], metodo=linha['metodo'], corpo_enviado=linha['corpo_enviado'],
            http_status=linha['http_status'], ret_code=linha['ret_code'], msg=linha['msg'],
            corpo_resposta=linha['corpo_resposta'], latencia_ms=linha['latencia_ms'], tentativa=linha['tentativa']))
    cli = gdms_client.GdmsClient(cfg.GDMS_CLIENT_ID, cfg.GDMS_CLIENT_SECRET, cfg.GDMS_BASE_URL,
                                 registrar=registrar, http=http)
    return cli


def _tentar_variantes_serial(conn, cli, tel, cr, cfg, resp_original):
    """O GDMS recusou o S/N. A etiqueta confunde O/0 e I/1: tenta as outras leituras. Se uma passar,
    grava o S/N certo no telefone e registra no audit. Devolve a resposta final do device/add."""
    resp = resp_original
    for sn in svc_tel.variantes_serial(tel['serial']):
        resp = cli.adicionar_aparelho(tel['mac'], sn, cr['id_rede'], cfg.GDMS_SITE_ID, cfg.GDMS_ORG_ID)
        status, _ = gdms_client.resultado_device_add(resp)
        if status == 'ok':
            conn.execute(update(db.telefones).where(db.telefones.c.id == tel['id']).values(serial=sn))
            auditoria.registrar(conn, 'serial_corrigido_automaticamente', 'sistema', 'gdms_fila', 'telefone', tel['id'],
                                detalhes={'de': tel['serial'], 'para': sn})
            return resp
        if status != 'serial_errado':
            return resp
    return resp


def interpretar(resposta):
    """Resposta do device/add -> 'ok' | 'conflito' | 'dados_invalidos' | 'temporario'."""
    status, _codigo = gdms_client.resultado_device_add(resposta)
    return STATUS_PARA_RESULTADO.get(status, 'temporario')


def processar(conn, cfg, http=None, ref=None, cliente=None):
    """Processa itens vencidos da fila. Retorna quantos foram tratados."""
    n = 0
    ref = ref or agora()
    for item in pendentes(conn, ref):
        n += 1
        tel = svc_tel.por_id(conn, item['telefone_id'])
        if item['etapa'] == 'teclas':
            if not tel or tel['estado'] not in ESTADOS_REENVIO or cfg.GDMS_MODO != 'real' or tel['modelo'] == 'ht':
                conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                             .values(estado='cancelada', atualizado_em=ref, ultima_msg='sem telefone no GDMS'))
                continue
            try:
                cli = cliente or criar_cliente(cfg, conn, tel['id'], http=http)
                if not cli.token_valido():
                    cli.obter_token(cfg.GDMS_USERNAME, cfg.GDMS_PASSWORD)
                cr = svc_cri.por_id(conn, tel['crianca_id'])
                from .. import grandstream_xml
                pv = grandstream_xml.pvalues_teclas(svc_tel.amigos_para_teclas(conn, cr), 'grp')
                xml = grandstream_xml.gerar_xml(tel['mac'], pv, tel['xml_versao'])
                resp = cli.configurar_xml(tel['mac'], xml, cfg.GDMS_ORG_ID, aplicar=True)
                ok, rc, msg = gdms_client.resultado_simples(resp)
            except Exception as e:
                ok, rc, msg = False, None, f'excecao: {type(e).__name__}: {e}'[:300]
            conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                         .values(estado='ok' if ok else 'erro', ultimo_ret_code=rc, ultima_msg=(msg or '')[:300], atualizado_em=ref))
            auditoria.registrar(conn, 'gdms_teclas_enviadas' if ok else 'gdms_teclas_falhou', 'sistema', 'gdms_fila',
                                'telefone', tel['id'], detalhes={'ret_code': rc, 'msg': (msg or '')[:120]})
            continue
        if item['etapa'] == 'config':
            # Retentativa so do envio da configuracao (E5); o device/add ja passou
            if not tel or tel['estado'] not in ESTADOS_REENVIO or cfg.GDMS_MODO != 'real':
                conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                             .values(estado='cancelada', atualizado_em=ref, ultima_msg='telefone fora dos estados de envio'))
                continue
            try:
                cli = cliente or criar_cliente(cfg, conn, tel['id'], http=http)
                if not cli.token_valido():
                    cli.obter_token(cfg.GDMS_USERNAME, cfg.GDMS_PASSWORD)
            except Exception as e:
                cli = None
                conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                             .values(ultima_msg=f'token: {e}'[:300]))
            if cli:
                enviar_config(conn, item, tel, cfg, cli, ref)
            continue
        if not tel or tel['estado'] != 'dados_informados':
            conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                         .values(estado='cancelada', atualizado_em=ref, ultima_msg='telefone fora de dados_informados'))
            continue
        tentativa = item['tentativas'] + 1
        if cfg.GDMS_MODO == 'desligado':
            conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                         .values(estado='cancelada', atualizado_em=ref, ultima_msg='GDMS desligado'))
            continue
        if cfg.GDMS_MODO == 'simulado':
            conn.execute(insert(db.gdms_log).values(ts=ref, request_id=auditoria.request_id(), telefone_id=tel['id'],
                                                    endpoint='device/add', metodo='SIMULADO', corpo_enviado={'mac': tel['mac']},
                                                    http_status=None, ret_code=0, msg='simulado', corpo_resposta=None,
                                                    latencia_ms=0, tentativa=tentativa))
            _ok(conn, item, tel, cfg, ref, simulado=True)
            continue
        # real
        try:
            cli = cliente or criar_cliente(cfg, conn, tel['id'], http=http)
            if not cli.token_valido():
                cli.obter_token(cfg.GDMS_USERNAME, cfg.GDMS_PASSWORD)
            cr = svc_cri.por_id(conn, tel['crianca_id'])
            # Idempotencia: se o MAC ja esta na nossa organizacao (retentativa apos timeout), nao re-adicionar
            try:
                ja = tel['mac'] in cli.macs_da_organizacao(cfg.GDMS_ORG_ID)
            except Exception:
                ja = False
            if ja:
                resp = {'retCode': 0, 'msg': 'ja cadastrado na organizacao (device/list)'}
            else:
                resp = cli.adicionar_aparelho(tel['mac'], tel['serial'], cr['id_rede'], cfg.GDMS_SITE_ID, cfg.GDMS_ORG_ID)
                status0, _ = gdms_client.resultado_device_add(resp)
                if status0 == 'serial_errado':
                    resp = _tentar_variantes_serial(conn, cli, tel, cr, cfg, resp)
            resultado = interpretar(resp)
            status, codigo = gdms_client.resultado_device_add(resp)
            rc = resp.get('retCode') if isinstance(resp, dict) else None
            msg = f'{status} {codigo or ""} {(resp.get("msg") if isinstance(resp, dict) else "") or ""}'.strip()
        except Exception as e:  # rede, token, etc.
            resultado, rc, msg = 'temporario', None, f'excecao: {type(e).__name__}: {e}'[:300]

        if resultado == 'ok':
            conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                         .values(tentativas=0, ultimo_ret_code=rc, ultima_msg=msg[:300]))
            item = dict(item, tentativas=0)
            _ok(conn, item, tel, cfg, ref, cliente=cli)
        elif resultado in ('conflito', 'dados_invalidos'):
            conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                         .values(estado='erro', tentativas=tentativa, ultimo_ret_code=rc, ultima_msg=msg[:300], atualizado_em=ref))
            evento = 'gdms_conflito' if resultado == 'conflito' else 'gdms_dados_invalidos'
            estados.transicionar(conn, tel['id'], evento, 'sistema', 'gdms_fila', detalhes={'ret_code': rc, 'msg': msg[:200]})
            _caso(conn, tel, 'gdms_conflito' if resultado == 'conflito' else 'gdms_dados_invalidos',
                  'alta' if resultado == 'conflito' else 'media',
                  f'GDMS recusou MAC {tel["mac"]}: retCode={rc} {msg[:120]}', {'ret_code': rc, 'msg': msg[:300]})
        else:
            if tentativa >= cfg.GDMS_MAX_TENTATIVAS:
                conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                             .values(estado='erro', tentativas=tentativa, ultimo_ret_code=rc, ultima_msg=msg[:300], atualizado_em=ref))
                estados.transicionar(conn, tel['id'], 'gdms_falha_persistente', 'sistema', 'gdms_fila',
                                     detalhes={'tentativas': tentativa, 'msg': msg[:200]})
                _caso(conn, tel, 'gdms_falha_persistente', 'alta',
                      f'{tentativa} tentativas de cadastrar MAC {tel["mac"]} no GDMS falharam: {msg[:120]}', {'msg': msg[:300]})
            else:
                espera = BACKOFF_MIN[min(tentativa - 1, len(BACKOFF_MIN) - 1)]
                conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                             .values(tentativas=tentativa, proxima_em=ref + timedelta(minutes=espera),
                                     ultimo_ret_code=rc, ultima_msg=msg[:300], atualizado_em=ref))
                auditoria.registrar(conn, 'gdms_cadastro_retentativa', 'sistema', 'gdms_fila', 'telefone', tel['id'],
                                    detalhes={'tentativa': tentativa, 'proxima_em_min': espera, 'msg': msg[:200]})
    return n


def _ok(conn, item, tel, cfg, ref, simulado=False, cliente=None):
    estados.transicionar(conn, tel['id'], 'gdms_ok', 'sistema', 'gdms_fila', detalhes={'simulado': simulado})
    tel = svc_tel.por_id(conn, tel['id'])
    # E5
    if simulado:
        _fila_concluida(conn, item, ref)
        estados.transicionar(conn, tel['id'], 'config_enviada', 'sistema', 'gdms_fila', detalhes={'metodo': 'simulado'})
        _avisar_pronto(conn, tel, cfg)
    elif cfg.GDMS_ENVIO_MODO == 'api':
        enviar_config(conn, item, tel, cfg, cliente, ref)
    else:
        _fila_concluida(conn, item, ref)
        _tarefa_manual(conn, tel, None)


def _fila_concluida(conn, item, ref):
    conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                 .values(estado='ok', atualizado_em=ref, ultimo_ret_code=0))


def enviar_config(conn, item, tel, cfg, cliente, ref):
    """E5 por API: POST device/config/xml com o XML do aparelho. Em falha, mantem o item na
    fila com etapa='config' e backoff; apos GDMS_MAX_TENTATIVAS cai para a tarefa manual."""
    tentativa = (item['tentativas'] or 0) + 1
    try:
        xml = svc_tel.gerar_xml_gdms(conn, tel, cfg)
        resp = cliente.configurar_xml(tel['mac'], xml, cfg.GDMS_ORG_ID, aplicar=True)
        ok, rc, msg = gdms_client.resultado_simples(resp)
    except Exception as e:
        ok, rc, msg = False, None, f'excecao: {type(e).__name__}: {e}'[:300]
    if ok:
        _fila_concluida(conn, item, ref)
        det = {'metodo': 'api', 'conteudo': cfg.GDMS_XML_CONTEUDO, 'xml_versao': tel['xml_versao']}
        if estados.pode(tel['estado'], 'config_enviada'):
            estados.transicionar(conn, tel['id'], 'config_enviada', 'sistema', 'gdms_fila', detalhes=det)
            _avisar_pronto(conn, tel, cfg)
        else:   # reenvio para telefone ja provisionado: estado nao muda, fica so o registro
            auditoria.registrar(conn, 'gdms_config_reenviada', 'sistema', 'gdms_fila', 'telefone', tel['id'], detalhes=det)
        return True
    if tentativa >= cfg.GDMS_MAX_TENTATIVAS:
        conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                     .values(estado='erro', etapa='config', tentativas=tentativa, ultimo_ret_code=rc, ultima_msg=msg[:300], atualizado_em=ref))
        _tarefa_manual(conn, tel, f'device/config/xml falhou {tentativa} vezes (retCode={rc} {msg[:100]})')
        return False
    espera = BACKOFF_MIN[min(tentativa - 1, len(BACKOFF_MIN) - 1)]
    conn.execute(update(db.gdms_fila).where(db.gdms_fila.c.id == item['id'])
                 .values(etapa='config', tentativas=tentativa, proxima_em=ref + timedelta(minutes=espera),
                         ultimo_ret_code=rc, ultima_msg=msg[:300], atualizado_em=ref))
    auditoria.registrar(conn, 'gdms_config_retentativa', 'sistema', 'gdms_fila', 'telefone', tel['id'],
                        detalhes={'tentativa': tentativa, 'proxima_em_min': espera, 'ret_code': rc, 'msg': msg[:200]})
    return False


def _tarefa_manual(conn, tel, observacao):
    desc = (f'Carregar a configuração do MAC {gdms_client.mac_para_gdms(tel["mac"])} no GDMS '
            f'(Dispositivo VoIP > Definir parâmetros > carregar XML gerado pelo portal)')
    if observacao:
        desc += f'. {observacao}'
    tid = conn.execute(insert(db.tarefas).values(tipo='enviar_config_gdms', telefone_id=tel['id'], descricao=desc,
                                                 estado='aberta', criado_em=agora())).inserted_primary_key[0]
    auditoria.registrar(conn, 'tarefa_operador_criada', 'sistema', 'gdms_fila', 'telefone', tel['id'],
                        detalhes={'tarefa_id': tid, 'tipo': 'enviar_config_gdms'})


def concluir_tarefa(conn, tarefa_id, operador_email, motivo, cfg):
    """Operador concluiu a tarefa manual. Para enviar_config_gdms, dispara config_enviada."""
    t = conn.execute(select(db.tarefas).where(db.tarefas.c.id == tarefa_id)).mappings().first()
    if not t or t['estado'] != 'aberta':
        raise ValueError('tarefa inexistente ou ja fechada')
    if not (motivo or '').strip():
        raise ValueError('motivo obrigatorio')
    conn.execute(update(db.tarefas).where(db.tarefas.c.id == tarefa_id)
                 .values(estado='concluida', concluido_em=agora(), concluido_por=operador_email, motivo=motivo))
    decorrido = (agora() - utc(t['criado_em'])).total_seconds() / 60 if t['criado_em'] else None
    auditoria.registrar(conn, 'tarefa_operador_concluida', 'operador', operador_email, 'telefone', t['telefone_id'],
                        detalhes={'tarefa_id': tarefa_id, 'tipo': t['tipo'], 'minutos': decorrido, 'motivo': motivo})
    if t['tipo'] == 'enviar_config_gdms' and t['telefone_id']:
        tel = svc_tel.por_id(conn, t['telefone_id'])
        if tel and estados.pode(tel['estado'], 'config_enviada'):
            estados.transicionar(conn, tel['id'], 'config_enviada', 'operador', operador_email, detalhes={'metodo': 'manual'})
            _avisar_pronto(conn, tel, cfg)


def _avisar_pronto(conn, tel, cfg):
    try:
        from flask import current_app
        mailer = current_app.mailer
    except RuntimeError:
        return
    cr = svc_cri.por_id(conn, tel['crianca_id'])
    fam = conn.execute(select(db.familias).where(db.familias.c.id == cr['familia_id'])).mappings().first() if cr else None
    if fam and '@' in fam['email'] and not fam['email'].startswith('excluida-'):
        mailer.enviar(fam['email'], f'Pode ligar o telefone de {cr["apelido"]} ({cfg.NOME_REDE})',
                      f'O telefone de {cr["apelido"]} está pronto. Ligue-o no roteador (cabo de rede) e na tomada.\n'
                      f'Acompanhe em {cfg.SITE_URL}/crianca/{cr["id"]}/telefone')


def _caso(conn, tel, tipo, gravidade, descricao, detalhes):
    cr = svc_cri.por_id(conn, tel['crianca_id'])
    conn.execute(insert(db.casos).values(tipo=tipo, gravidade=gravidade, telefone_id=tel['id'], crianca_id=tel['crianca_id'],
                                         familia_id=cr['familia_id'] if cr else None, descricao=descricao,
                                         detalhes=detalhes, estado='aberto', criado_em=agora()))
