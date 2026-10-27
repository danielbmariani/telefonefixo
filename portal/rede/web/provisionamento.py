"""provisionamento.py — E7: GET /p/<token>/cfg<mac>.xml. Sem login. Toda requisicao vai para prov_log."""

from flask import Blueprint, Response, abort, current_app, g, request

from .. import seguranca, db
from ..servicos import telefones as svc_tel
from .comum import conn

bp = Blueprint('prov', __name__)


@bp.route('/p/<token>/cfg<mac>.xml')
def cfg_xml(token, mac):
    ip = g.ip
    # Rate limit por IP: um telefone pede 1x por boot e 1x por dia
    if seguranca.excedeu(f'prov:{ip}', 60, 3600):
        conn().execute(db.prov_log.insert().values(ts=__import__('rede.tempo', fromlist=['agora']).agora(), ip=ip,
                                                   user_agent=g.user_agent, mac_pedido=mac[:12].upper(), resultado='rate_limit',
                                                   request_id=g.request_id))
        abort(429)
    seguranca.registrar_tentativa(f'prov:{ip}')
    xml, resultado = svc_tel.entregar_config(conn(), token, mac, ip, g.user_agent, current_app.cfg)
    if xml is None:
        abort(404)   # mesma resposta para token inexistente, MAC errado e estado invalido
    resp = Response(xml, mimetype='text/xml')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@bp.route('/p/<token>/')
@bp.route('/p/<token>/<path:resto>')
def outros(token, resto=''):
    """cfg.xml, cfgMODELO.xml etc.: nao servimos nada generico. 404 sem distincao."""
    abort(404)
