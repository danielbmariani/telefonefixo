#!/usr/bin/env python3
"""
gdms_client.py — Cliente minimo da API do GDMS (Grandstream Device Management
System) para o caminho 3 (zero-touch). Esboco para validacao em bancada.

Baseado no GDMS API Guide (documentation.grandstream.com/knowledge-base/gdms-api-guide/):

  Token:      POST https://www.gdms.cloud/oapi/oauth/token
              username, password=SHA256(MD5(senha)), grant_type=password,
              client_id, client_secret
  Refresh:    mesma URL, grant_type=refresh_token, refresh_token, client_id, client_secret
  Assinatura: SHA256 de "&access_token=T&client_id=C&client_secret=S&timestamp=MS&"
              Em POST com corpo: inserir SHA256(corpo) antes do "&" final:
              "&access_token=T&client_id=C&client_secret=S&timestamp=MS&<sha256 corpo>&"
              Com parametros extras na query (ex.: orgId): TODOS os parametros entram na base,
              em ordem alfabetica de nome (confirmado na bancada B03b, 2026-10-23; sem isso
              a API devolve retCode 40003 "bad signature").
  Query:      access_token, signature, timestamp (epoch em milissegundos)
  Endpoints:  GET  /oapi/v1.0.0/org/list
              GET  /oapi/v1.0.0/site/list
              POST /oapi/v1.0.0/device/add   [{"deviceName","mac","sn","siteId","orgId"}]
              POST /oapi/v1.0.0/task/add     {"taskName","taskType","macList","execType"}
              POST /oapi/v1.0.0/device/list  {"orgId","pageNum","pageSize"} -> data.result[], data.total
                                              (nao esta no guia; confirmado na bancada 2026-10-23)
  Resposta:   {"retCode": 0, "msg": "", "data": {...}}   retCode 0 = sucesso
  Confirmado: token expira em 86399 s (24 h); retCode 40003 = "bad signature".

Referencia completa (api_data.js do doc.grandstream.dev, lida em 2026-10-23; resumo em
bancada/B06-api-referencia.md). Alem dos acima:
  POST device/config/xml          multipart: xml=<arquivo>, mac, orgId, applyConfig  -> entrega
                                  um cfg XML ao aparelho (E5 sem operador). Assinatura de
                                  formulario: cada campo entra na base; arquivo entra como
                                  md5(conteudo) em minusculas.
  POST device/site/config/xml     xml para todos os aparelhos do site; applyAddDevice=true
                                  aplica tambem aos que forem adicionados depois.
  POST device/account/status      {mac} -> contas SIP e status de registro vistos pelo GDMS
  POST device/delete              {macList, orgId}
  POST callback/set_url           {callbackUrl}  (o GDMS testa a URL na hora: 26023/26024)
  POST subscribe/save             assina eventos: deviceStatus/accountStatus por org e
                                  alertas (0 falha de registro, 2 reset de fabrica, 5 reboot,
                                  7 tarefa falhou, 9 offline)
  POST subscribe/info, subscribe/delete, subscribe/available_options
  POST template/modelTemplate/list, template/push/config {macs, id, templateType 2}
  POST sip/server/*, sip/account/*  (nao usados: a conta SIP vai no XML)
Nao existe RPS na API (so na interface). Os callbacks do GDMS nao sao assinados.

Auditoria: toda chamada passa por `registrar`, que recebe um dicionario pronto
para a tabela gdms_log COM SEGREDOS REDIGIDOS. O chamador decide onde gravar
(em testes, uma lista em memoria).

Sem dependencias externas (urllib). Modo --dry-run monta as requisicoes sem
enviar, para inspecionar assinatura e corpo.
"""

import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request

BASE_URL_US = 'https://www.gdms.cloud'
BASE_URL_EU = 'https://eu.gdms.cloud'
API_PREFIX = '/oapi/v1.0.0/'

MAC_RE = re.compile(r'^[0-9A-F]{12}$')
# Prefixos (OUI) da Grandstream vistos em campo; ampliar conforme a bancada
OUIS_GRANDSTREAM = {'000B82', 'C074AD', 'EC74D7'}


# --- Funcoes puras (testaveis sem rede) ---

def hash_senha(senha):
    """password do token = SHA256(hex(MD5(senha)))."""
    md5 = hashlib.md5(senha.encode('utf-8')).hexdigest()
    return hashlib.sha256(md5.encode('utf-8')).hexdigest()


def timestamp_ms(agora=None):
    return str(int((agora if agora is not None else time.time()) * 1000))


def hash_corpo(corpo_json):
    """SHA256 do corpo JSON exatamente como sera enviado (string)."""
    return hashlib.sha256(corpo_json.encode('utf-8')).hexdigest()


def montar_base_assinatura(access_token, client_id, client_secret, ts_ms, corpo_json=None, params=None):
    todos = {'access_token': access_token, 'client_id': client_id, 'client_secret': client_secret,
             'timestamp': ts_ms, **(params or {})}
    base = '&' + '&'.join(f'{k}={todos[k]}' for k in sorted(todos)) + '&'
    if corpo_json is not None:
        base += hash_corpo(corpo_json) + '&'
    return base


def assinar(access_token, client_id, client_secret, ts_ms, corpo_json=None, params=None):
    base = montar_base_assinatura(access_token, client_id, client_secret, ts_ms, corpo_json, params)
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def md5_arquivo(conteudo):
    """Valor que um campo de arquivo assume na base da assinatura (md5 minusculo)."""
    return hashlib.md5(conteudo).hexdigest()


def montar_base_formulario(access_token, client_id, client_secret, ts_ms, campos, arquivos, params=None):
    """Base da assinatura para envio multipart (Signature Method, item 4): campos do
    formulario e da query entram como key=value; arquivos entram como md5(conteudo).
    Tudo em ordem alfabetica, entre '&'."""
    todos = {'access_token': access_token, 'client_id': client_id, 'client_secret': client_secret,
             'timestamp': ts_ms, **(params or {}), **{k: str(v) for k, v in campos.items()},
             **{k: md5_arquivo(conteudo) for k, (_nome, conteudo) in arquivos.items()}}
    return '&' + '&'.join(f'{k}={todos[k]}' for k in sorted(todos)) + '&'


def assinar_formulario(access_token, client_id, client_secret, ts_ms, campos, arquivos, params=None):
    base = montar_base_formulario(access_token, client_id, client_secret, ts_ms, campos, arquivos, params)
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def montar_multipart(campos, arquivos, boundary):
    """Corpo multipart/form-data (bytes). arquivos: {campo: (nome_arquivo, bytes)}."""
    partes = []
    for k, v in campos.items():
        partes.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode('utf-8'))
    for k, (nome, conteudo) in arquivos.items():
        partes.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{nome}"\r\n'
                       f'Content-Type: application/xml\r\n\r\n').encode('utf-8') + conteudo + b'\r\n')
    partes.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(partes)


def mac_para_gdms(mac):
    """Qualquer formato -> 'XY:XY:XY:XY:XY:XY' maiusculo (formato exigido pela API).
    Valida 12 hex e, opcionalmente, o prefixo de fabricante."""
    limpo = re.sub(r'[^0-9A-Fa-f]', '', mac or '').upper()
    if not MAC_RE.match(limpo):
        raise ValueError(f'MAC invalido: {mac!r}')
    return ':'.join(limpo[i:i + 2] for i in range(0, 12, 2))


def mac_e_grandstream(mac):
    limpo = re.sub(r'[^0-9A-Fa-f]', '', mac or '').upper()
    return len(limpo) == 12 and limpo[:6] in OUIS_GRANDSTREAM


def validar_serial(sn):
    """Serial da etiqueta: alfanumerico, 8 a 32 caracteres. Formato exato a
    confirmar na bancada com aparelhos reais."""
    s = re.sub(r'\s', '', sn or '').upper()
    if not re.match(r'^[A-Z0-9]{8,32}$', s):
        raise ValueError('Numero de serie invalido')
    return s


def redigir(obj, chaves=('password', 'client_secret', 'access_token', 'refresh_token', 'signature')):
    """Copia de dicionario/lista com segredos substituidos por '***' (para log)."""
    if isinstance(obj, dict):
        return {k: ('***' if k in chaves else redigir(v, chaves)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redigir(v, chaves) for v in obj]
    return obj


def corpo_device_add(mac, sn, device_name, site_id, org_id):
    """Corpo do device/add. device_name deve ser o ID da crianca, nunca apelido
    ou e-mail (minimizacao de dados enviados a terceiro).
    Bancada 2026-10-23: o siteId precisa pertencer a organizacao (cada org tem o
    proprio site 'Default'); um siteId de outra org da errorMsg 50025. Omitir o
    siteId (0/None) coloca o aparelho no site padrao da org, que e o que queremos."""
    if not re.match(r'^[0-9A-Za-z_-]{1,40}$', device_name):
        raise ValueError('deviceName deve ser o ID (sem dados pessoais)')
    item = {
        'deviceName': device_name,
        'mac': mac_para_gdms(mac),
        'sn': validar_serial(sn),
        'orgId': int(org_id),
    }
    if site_id:
        item['siteId'] = int(site_id)
    return [item]


# Codigos por aparelho em data.errorDeviceList[].errorMsg. Tabela oficial da referencia
# (doc.grandstream.dev, Device Interfaces > Add Device), confirmada em parte na bancada 2026-10-23:
ERROS_DEVICE_ADD = {
    '30007': 'ja_na_organizacao',        # "device mac exists" (confirmado)
    '30011': 'em_outra_organizacao',     # "device exists another company" (confirmado entre orgs da mesma conta)
    '30010': 'serial_errado',            # "device sn Error"
    '30012': 'modelo_nao_suportado',     # "device type not support" (ex.: GXP1610)
    '50025': 'site_invalido',            # "This data does not exist under this organization" (siteId de outra org; confirmado)
    '20002': 'site_invalido',            # "site not exist"
    '50007': 'mac_invalido',             # "invalid mac"
    '30003': 'serial_errado',            # "device sn is Empty"
}
# Outros da referencia: 50024 data out of limit (max 100 por chamada), 14007/14009 conta sem org,
# 50005 Param invalid, 13000 check device error, 50012 erp system error, 30032 device erp has existed.


def resultado_device_add(resp):
    """Interpreta a resposta do device/add, que devolve retCode 0 mesmo quando o
    aparelho falha: o detalhe vem em data.success/failure/errorDeviceList.
    Retorna (status, codigo): status em 'ok' | 'ja_na_organizacao' | 'em_outra_organizacao'
    | 'serial_errado' | 'modelo_nao_suportado' | 'site_invalido' | 'mac_invalido'
    | 'erro_desconhecido' | 'temporario'."""
    if not isinstance(resp, dict) or resp.get('retCode') != 0:
        return 'temporario', (resp or {}).get('retCode') if isinstance(resp, dict) else None
    dados = resp.get('data') or {}
    if dados.get('success', 0) >= 1 and not dados.get('failure'):
        return 'ok', None
    erros = dados.get('errorDeviceList') or []
    if not erros:
        return 'erro_desconhecido', None
    codigo = str(erros[0].get('errorMsg', ''))
    return ERROS_DEVICE_ADD.get(codigo, 'erro_desconhecido'), codigo


# --- Cliente ---

class GdmsClient:
    def __init__(self, client_id, client_secret, base_url=BASE_URL_US,
                 registrar=None, dry_run=False, http=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip('/')
        self.registrar = registrar or (lambda linha: None)
        self.dry_run = dry_run
        self._http = http or self._http_padrao
        self.access_token = None
        self.refresh_token = None
        self.token_obtido_em = 0

    # -- transporte --
    @staticmethod
    def _http_padrao(metodo, url, corpo=None, headers=None, timeout=20):
        dados = corpo.encode('utf-8') if isinstance(corpo, str) else corpo
        req = urllib.request.Request(url, data=dados or None, method=metodo, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace')

    def _log(self, endpoint, metodo, enviado, status, resposta, latencia_ms, tentativa=1):
        try:
            resp_obj = json.loads(resposta) if resposta else None
        except ValueError:
            resp_obj = {'raw': resposta[:500]}
        self.registrar({
            'ts': time.time(),
            'endpoint': endpoint,
            'metodo': metodo,
            'corpo_enviado': redigir(enviado),
            'http_status': status,
            'ret_code': (resp_obj or {}).get('retCode') if isinstance(resp_obj, dict) else None,
            'msg': (resp_obj or {}).get('msg') if isinstance(resp_obj, dict) else None,
            'corpo_resposta': redigir(resp_obj),
            'latencia_ms': latencia_ms,
            'tentativa': tentativa,
        })
        return resp_obj

    # -- autenticacao --
    def obter_token(self, username, senha):
        params = {
            'username': username,
            'password': hash_senha(senha),
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        return self._token(params)

    def renovar_token(self):
        if not self.refresh_token:
            raise RuntimeError('sem refresh_token')
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        return self._token(params)

    def _token(self, params):
        url = self.base_url + '/oapi/oauth/token'
        corpo = urllib.parse.urlencode(params)
        if self.dry_run:
            self._log('oauth/token', 'POST', params, None, '', 0)
            return {'dry_run': True, 'url': url, 'params': redigir(params)}
        ini = time.time()
        status, resposta = self._http('POST', url, corpo, {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'})
        obj = self._log('oauth/token', 'POST', params, status, resposta, int((time.time() - ini) * 1000))
        if not isinstance(obj, dict) or 'access_token' not in obj:
            raise RuntimeError(f'token falhou: HTTP {status}')
        self.access_token = obj['access_token']
        self.refresh_token = obj.get('refresh_token')
        self.token_obtido_em = time.time()
        return obj

    def token_valido(self):
        # O guia manda renovar a cada hora
        return bool(self.access_token) and (time.time() - self.token_obtido_em) < 3300

    # -- chamadas assinadas --
    def _url_assinada(self, caminho, corpo_json=None, ts_ms=None, params=None):
        ts = ts_ms or timestamp_ms()
        sig = assinar(self.access_token, self.client_id, self.client_secret, ts, corpo_json, params)
        q = urllib.parse.urlencode({'access_token': self.access_token, 'signature': sig, 'timestamp': ts, **(params or {})})
        return f'{self.base_url}{API_PREFIX}{caminho}?{q}'

    def get(self, caminho, params=None):
        if not self.dry_run and not self.token_valido():
            self.renovar_token()
        url = self._url_assinada(caminho, params=params)
        if self.dry_run:
            self._log(caminho, 'GET', None, None, '', 0)
            return {'dry_run': True, 'url': redigir_url(url)}
        ini = time.time()
        status, resposta = self._http('GET', url, None, {'Accept': 'application/json'})
        return self._log(caminho, 'GET', None, status, resposta, int((time.time() - ini) * 1000))

    def post(self, caminho, corpo_obj):
        corpo_json = json.dumps(corpo_obj, separators=(',', ':'), ensure_ascii=False)
        if not self.dry_run and not self.token_valido():
            self.renovar_token()
        url = self._url_assinada(caminho, corpo_json)
        if self.dry_run:
            self._log(caminho, 'POST', corpo_obj, None, '', 0)
            return {'dry_run': True, 'url': redigir_url(url), 'corpo': corpo_json}
        ini = time.time()
        status, resposta = self._http('POST', url, corpo_json, {
            'Accept': 'application/json', 'Content-Type': 'application/json'})
        return self._log(caminho, 'POST', corpo_obj, status, resposta, int((time.time() - ini) * 1000))

    def post_form(self, caminho, campos, arquivos, params=None):
        """POST multipart/form-data assinado (device/config/xml, device/site/config/xml).
        arquivos: {campo: (nome_arquivo, bytes)}. No log, o arquivo vira seu md5 e tamanho."""
        if not self.dry_run and not self.token_valido():
            self.renovar_token()
        ts = timestamp_ms()
        sig = assinar_formulario(self.access_token, self.client_id, self.client_secret, ts, campos, arquivos, params)
        q = urllib.parse.urlencode({'access_token': self.access_token, 'signature': sig, 'timestamp': ts, **(params or {})})
        url = f'{self.base_url}{API_PREFIX}{caminho}?{q}'
        boundary = '----rede-aberta-' + hashlib.sha1(ts.encode()).hexdigest()[:16]
        corpo = montar_multipart(campos, arquivos, boundary)
        enviado = {**campos, **{k: {'arquivo': nome, 'md5': md5_arquivo(c), 'bytes': len(c)} for k, (nome, c) in arquivos.items()}}
        if self.dry_run:
            self._log(caminho, 'POST', enviado, None, '', 0)
            return {'dry_run': True, 'url': redigir_url(url), 'campos': enviado, 'base_assinatura':
                    redigir_url(montar_base_formulario('***', '***', '***', ts, campos, arquivos, params))}
        ini = time.time()
        status, resposta = self._http('POST', url, corpo, {
            'Accept': 'application/json', 'Content-Type': f'multipart/form-data; boundary={boundary}'})
        return self._log(caminho, 'POST', enviado, status, resposta, int((time.time() - ini) * 1000))

    # -- operacoes de negocio --
    def listar_orgs(self):
        return self.get('org/list')

    def listar_sites(self, org_id=None):
        return self.get('site/list', {'orgId': int(org_id)} if org_id else None)

    def listar_aparelhos(self, org_id, pagina=1, por_pagina=100):
        """POST device/list (confirmado na bancada). Retorna a resposta bruta."""
        return self.post('device/list', {'orgId': int(org_id), 'pageNum': int(pagina), 'pageSize': int(por_pagina)})

    def macs_da_organizacao(self, org_id):
        """Conjunto de MACs (12 hex maiusculos) cadastrados na organizacao, paginando."""
        macs, pagina = set(), 1
        while True:
            r = self.listar_aparelhos(org_id, pagina, 100)
            if not isinstance(r, dict) or r.get('retCode') != 0:
                raise RuntimeError(f'device/list falhou: {r}')
            dados = r.get('data') or {}
            for item in dados.get('result') or []:
                mac = item.get('mac') or item.get('macAddress') or ''
                limpo = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
                if len(limpo) == 12:
                    macs.add(limpo)
            total = dados.get('total') or 0
            if pagina * 100 >= total or not dados.get('result'):
                return macs
            pagina += 1

    def adicionar_aparelho(self, mac, sn, device_name, site_id, org_id):
        """E4 do fluxo. Retorna a resposta bruta; o chamador interpreta retCode
        com a tabela de codigos levantada na bancada."""
        return self.post('device/add', corpo_device_add(mac, sn, device_name, site_id, org_id))

    def remover_aparelhos(self, macs, org_id):
        """POST device/delete {macList, orgId} (referencia: ate 100 por chamada)."""
        return self.post('device/delete', {'macList': [mac_para_gdms(m) for m in macs], 'orgId': int(org_id)})

    def reiniciar_aparelhos(self, macs):
        corpo = {'taskName': 'REBOOT', 'taskType': 1,
                 'macList': [mac_para_gdms(m) for m in macs], 'execType': 1}
        return self.post('task/add', corpo)

    # E5: entrega da configuracao pelo GDMS
    def configurar_xml(self, mac, xml, org_id, aplicar=True):
        """POST device/config/xml. O GDMS guarda o XML como configuracao do aparelho e
        entrega quando ele estiver online (comportamento com aparelho offline: B06b)."""
        conteudo = xml.encode('utf-8') if isinstance(xml, str) else xml
        campos = {'mac': mac_para_gdms(mac), 'orgId': str(int(org_id)), 'applyConfig': 'true' if aplicar else 'false'}
        return self.post_form('device/config/xml', campos, {'xml': ('cfg.xml', conteudo)})

    def configurar_xml_site(self, xml, org_id, site_id=None, aplicar_aos_novos=True):
        """POST device/site/config/xml: XML base para todos os aparelhos do site, inclusive os
        adicionados depois (applyAddDevice). Util para travas e parametros comuns, sem segredo."""
        conteudo = xml.encode('utf-8') if isinstance(xml, str) else xml
        campos = {'orgId': str(int(org_id)), 'applyAddDevice': 'true' if aplicar_aos_novos else 'false'}
        if site_id:
            campos['siteId'] = str(int(site_id))
        return self.post_form('device/site/config/xml', campos, {'xml': ('site.xml', conteudo)})

    def status_contas(self, mac):
        """POST device/account/status {mac} -> data.sipAccountInfoList[] (accountStatus Up/Disabled)."""
        return self.post('device/account/status', {'mac': mac_para_gdms(mac)})

    def detalhe_aparelho(self, mac, primeira=True):
        """POST device/detail (so com aparelho online; isFirst=1 na primeira chamada)."""
        return self.post('device/detail', {'mac': mac_para_gdms(mac), 'isFirst': 1 if primeira else 0})

    # Eventos (webhook)
    def definir_callback(self, url):
        """POST callback/set_url. O GDMS chama a URL na hora para validar (26023 recusado, 26024 timeout)."""
        return self.post('callback/set_url', {'callbackUrl': url})

    def assinar_eventos(self, org_id, alertas=(0, 2, 5, 7, 9)):
        """POST subscribe/save: status de aparelho/conta e alertas da organizacao.
        Sobrescreve a assinatura anterior (a API nao faz merge)."""
        corpo = {
            'device': {'voip': {'orgType': 1, 'subscrList': [{'orgId': int(org_id), 'contents': ['deviceStatus', 'accountStatus']}]}},
            'alert': {'voip': {'orgType': 1, 'subscrList': [{'orgId': int(org_id), 'contents': list(alertas)}]}},
        }
        return self.post('subscribe/save', corpo)

    def consultar_assinatura(self):
        return self.post('subscribe/info', {})

    def eventos_disponiveis(self):
        return self.post('subscribe/available_options', {})

    # Templates (so leitura/push; criacao e pela interface)
    def listar_templates_modelo(self, org_id, pagina=1, por_pagina=50):
        return self.post('template/modelTemplate/list', {'orgId': str(int(org_id)), 'pageNum': pagina, 'pageSize': por_pagina})

    def criar_tarefa(self, macs, tipo, org_id, nome=None):
        """POST task/add: tipo 1 = reboot, 2 = reset de fabrica, 3 = upgrade (nao usamos). Imediata.
        Uso na bancada (B11) e, no futuro, para reiniciar um telefone travado sem a familia mexer."""
        nomes = {1: 'reiniciar', 2: 'reset-de-fabrica'}
        return self.post('task/add', {'taskName': (nome or f'portal-{nomes.get(int(tipo), tipo)}')[:64], 'taskType': int(tipo),
                                      'macList': [mac_para_gdms(m) for m in macs], 'execType': 1, 'orgId': int(org_id)})

    def empurrar_template(self, macs, template_id, tipo=2):
        """POST template/push/config: tipo 2 = por modelo, 1 = por grupo. data.failureMacs lista falhas."""
        return self.post('template/push/config', {'macs': [mac_para_gdms(m) for m in macs], 'id': int(template_id), 'templateType': int(tipo)})


def resultado_simples(resp):
    """Para endpoints que respondem so retCode/msg (config/xml, callback, subscribe).
    Retorna (ok, codigo, msg)."""
    if not isinstance(resp, dict):
        return False, None, 'resposta invalida'
    rc = resp.get('retCode')
    return rc == 0, rc, (resp.get('msg') or '')


def redigir_url(url):
    return re.sub(r'(access_token|signature)=[^&]+', r'\1=***', url)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description='Cliente GDMS (bancada)')
    p.add_argument('--client-id', required=True)
    p.add_argument('--client-secret', required=True)
    p.add_argument('--username')
    p.add_argument('--password')
    p.add_argument('--eu', action='store_true', help='usar eu.gdms.cloud')
    p.add_argument('--dry-run', action='store_true')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('orgs')
    s = sub.add_parser('sites'); s.add_argument('--org-id', type=int)
    d = sub.add_parser('devices'); d.add_argument('--org-id', type=int, required=True)
    a = sub.add_parser('add')
    a.add_argument('--mac', required=True)
    a.add_argument('--sn', required=True)
    a.add_argument('--id', required=True, help='ID da crianca (deviceName)')
    a.add_argument('--site-id', type=int, default=0, help='omitir = site padrao da org')
    a.add_argument('--org-id', required=True, type=int)
    x = sub.add_parser('config-xml', help='E5: envia um cfg XML ao aparelho pelo GDMS')
    x.add_argument('--mac', required=True); x.add_argument('--org-id', required=True, type=int)
    x.add_argument('--xml', required=True, help='caminho do arquivo XML')
    x.add_argument('--sem-aplicar', action='store_true')
    st = sub.add_parser('status'); st.add_argument('--mac', required=True)
    dt = sub.add_parser('detail'); dt.add_argument('--mac', required=True)
    de = sub.add_parser('delete'); de.add_argument('--mac', required=True); de.add_argument('--org-id', required=True, type=int)
    tk = sub.add_parser('tarefa', help='1 reboot, 2 reset de fabrica'); tk.add_argument('--mac', required=True)
    tk.add_argument('--tipo', type=int, required=True, choices=[1, 2]); tk.add_argument('--org-id', required=True, type=int)
    cb = sub.add_parser('callback'); cb.add_argument('--url', required=True)
    ev = sub.add_parser('assinar-eventos'); ev.add_argument('--org-id', required=True, type=int)
    sub.add_parser('assinatura')
    sub.add_parser('eventos-disponiveis')
    tm = sub.add_parser('templates'); tm.add_argument('--org-id', required=True, type=int)
    args = p.parse_args(argv)

    log = []
    cli = GdmsClient(args.client_id, args.client_secret,
                     BASE_URL_EU if args.eu else BASE_URL_US,
                     registrar=log.append, dry_run=args.dry_run)
    if args.dry_run:
        cli.access_token = 'TOKEN_DRY_RUN'
    else:
        cli.obter_token(args.username, args.password)

    if args.cmd == 'orgs':
        r = cli.listar_orgs()
    elif args.cmd == 'sites':
        r = cli.listar_sites(args.org_id)
    elif args.cmd == 'devices':
        r = cli.listar_aparelhos(args.org_id)
    elif args.cmd == 'add':
        r = cli.adicionar_aparelho(args.mac, args.sn, args.id, args.site_id, args.org_id)
    elif args.cmd == 'config-xml':
        with open(args.xml, 'rb') as f:
            r = cli.configurar_xml(args.mac, f.read(), args.org_id, aplicar=not args.sem_aplicar)
    elif args.cmd == 'status':
        r = cli.status_contas(args.mac)
    elif args.cmd == 'detail':
        r = cli.detalhe_aparelho(args.mac)
    elif args.cmd == 'delete':
        r = cli.remover_aparelhos([args.mac], args.org_id)
    elif args.cmd == 'tarefa':
        r = cli.criar_tarefa([args.mac], args.tipo, args.org_id)
    elif args.cmd == 'callback':
        r = cli.definir_callback(args.url)
    elif args.cmd == 'assinar-eventos':
        r = cli.assinar_eventos(args.org_id)
    elif args.cmd == 'assinatura':
        r = cli.consultar_assinatura()
    elif args.cmd == 'eventos-disponiveis':
        r = cli.eventos_disponiveis()
    else:
        r = cli.listar_templates_modelo(args.org_id)

    print(json.dumps(r, indent=2, ensure_ascii=False))
    print('--- gdms_log (redigido) ---', file=sys.stderr)
    for linha in log:
        print(json.dumps(linha, ensure_ascii=False, default=str), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
