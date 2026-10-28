"""ari.py — Cliente REST minimo do ARI (Asterisk REST Interface), so o que a chamada em grupo usa."""

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger('rede.grupo.ari')


class ErroAri(Exception):
    pass


class Ari:
    def __init__(self, url, usuario, senha, timeout=5):
        self.url = url.rstrip('/')
        self.auth = base64.b64encode(f'{usuario}:{senha}'.encode()).decode()
        self.timeout = timeout

    def _req(self, metodo, caminho, params=None, corpo=None):
        q = ('?' + urllib.parse.urlencode(params, doseq=True)) if params else ''
        dados = json.dumps(corpo).encode() if corpo is not None else None
        r = urllib.request.Request(self.url + caminho + q, data=dados, method=metodo)
        r.add_header('Authorization', 'Basic ' + self.auth)
        if dados is not None:
            r.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(r, timeout=self.timeout) as resp:
                txt = resp.read().decode() or ''
                return json.loads(txt) if txt.strip() else None
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors='replace')[:200]
            raise ErroAri(f'{metodo} {caminho}: HTTP {e.code} {txt}') from None
        except urllib.error.URLError as e:
            raise ErroAri(f'{metodo} {caminho}: {e}') from None

    # canais
    def answer(self, canal):
        self._req('POST', f'/channels/{canal}/answer')

    def hangup(self, canal):
        try:
            self._req('DELETE', f'/channels/{canal}')
        except ErroAri as e:
            if 'HTTP 404' not in str(e):
                raise

    def play_channel(self, canal, medias):
        r = self._req('POST', f'/channels/{canal}/play', {'media': ','.join(medias)})
        return r['id']

    def originate(self, endpoint, app, app_args, caller_id, timeout, channel_id, variaveis=None):
        self._req('POST', '/channels', {'endpoint': endpoint, 'app': app, 'appArgs': app_args, 'callerId': caller_id,
                                        'timeout': timeout, 'channelId': channel_id},
                  {'variables': variaveis or {}})
        return channel_id

    # pontes
    def create_bridge(self, nome):
        r = self._req('POST', '/bridges', {'type': 'mixing', 'name': nome})
        return r['id']

    def destroy_bridge(self, ponte):
        try:
            self._req('DELETE', f'/bridges/{ponte}')
        except ErroAri as e:
            if 'HTTP 404' not in str(e):
                raise

    def add_channel(self, ponte, canal):
        self._req('POST', f'/bridges/{ponte}/addChannel', {'channel': canal})

    def play_bridge(self, ponte, medias):
        r = self._req('POST', f'/bridges/{ponte}/play', {'media': ','.join(medias)})
        return r['id']

    def moh_bridge(self, ponte, classe):
        self._req('POST', f'/bridges/{ponte}/moh', {'mohClass': classe})

    def stop_moh_bridge(self, ponte):
        try:
            self._req('DELETE', f'/bridges/{ponte}/moh')
        except ErroAri:
            pass

    def channels(self):
        return self._req('GET', '/channels') or []

    def info(self):
        return self._req('GET', '/asterisk/info', {'only': 'system'})
