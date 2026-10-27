"""gdms_eventos.py — POST /gdms/eventos/<segredo>: webhook do GDMS. Sem login, sem CSRF."""

import hmac

from flask import Blueprint, abort, current_app, g, jsonify, request

from .. import seguranca
from ..servicos import gdms_eventos as svc
from .comum import conn

bp = Blueprint('gdms_eventos', __name__)


@bp.route('/gdms/eventos/<segredo>', methods=['POST'])
def receber(segredo):
    esperado = current_app.cfg.GDMS_WEBHOOK_SEGREDO or ''
    if not esperado or not hmac.compare_digest(segredo, esperado):
        abort(404)
    if seguranca.excedeu(f'gdms-cb:{g.ip}', 600, 60):
        abort(429)
    seguranca.registrar_tentativa(f'gdms-cb:{g.ip}')
    corpo = request.get_json(silent=True)
    if corpo is None:
        corpo = {}
    res = svc.processar(conn(), corpo, g.ip, current_app.cfg)
    return jsonify({'retCode': 0, 'msg': '', 'data': res})
