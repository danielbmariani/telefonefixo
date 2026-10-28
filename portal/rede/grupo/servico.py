"""servico.py — Processo rede-grupo: liga no websocket de eventos do ARI e entrega cada evento ao AppGrupo.

Uso: /opt/rede-aberta/venv/bin/python -m rede.grupo.servico (systemd rede-grupo.service, usuario rede,
EnvironmentFile /etc/rede-aberta/portal.env). Reconecta sozinho se o Asterisk reiniciar.
"""

import asyncio
import json
import logging
import time
import urllib.parse

from .. import db
from ..config import Config
from .ari import Ari
from .app import AppGrupo, APP

log = logging.getLogger('rede.grupo.servico')


class Timer:
    def __init__(self, handle):
        self.handle = handle

    def cancel(self):
        self.handle.cancel()


async def rodar(cfg):
    engine = db.criar_engine(cfg.DATABASE_URL)
    ari = Ari(cfg.ARI_URL, cfg.ARI_USUARIO, cfg.ARI_SENHA)
    loop = asyncio.get_running_loop()
    app = AppGrupo(ari, engine, cfg, time.time, lambda s, fn: Timer(loop.call_later(s, fn)))
    import websockets  # dependencia so deste servico
    base = cfg.ARI_URL.replace('http://', 'ws://').replace('https://', 'wss://')
    url = f'{base}/events?' + urllib.parse.urlencode({'app': APP, 'api_key': f'{cfg.ARI_USUARIO}:{cfg.ARI_SENHA}',
                                                       'subscribeAll': 'false'})
    espera = 1
    while True:
        try:
            async with websockets.connect(url, max_size=2 ** 20, ping_interval=20) as ws:
                log.info('conectado ao ARI, app %s', APP)
                espera = 1
                async for msg in ws:
                    try:
                        ev = json.loads(msg)
                    except ValueError:
                        continue
                    app.evento(ev)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning('ARI desconectado (%s); tentando em %ss', e, espera)
            await asyncio.sleep(espera)
            espera = min(espera * 2, 30)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    cfg = Config()
    if not cfg.ARI_SENHA:
        raise SystemExit('REDE_ARI_SENHA nao definida em /etc/rede-aberta/portal.env')
    asyncio.run(rodar(cfg))


if __name__ == '__main__':
    main()
