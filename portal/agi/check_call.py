#!/opt/rede-aberta/venv/bin/python3
"""check_call.py — AGI: decide se a chamada pode acontecer (rede aberta, IDs de 6 digitos).
Logica em rede/servicos/chamadas.py (testada sem Asterisk). Fail-closed."""

import sys
from datetime import datetime

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402


def main():
    env = A.agi_read_env()
    caller = A.caller_de(env)
    destino = env.get('agi_arg_1') or env.get('agi_extension', '')
    A.agi_verbose(f'check_call: caller={caller} dest={destino}')
    try:
        from rede.servicos import chamadas
        from rede.tempo import TZ_SP
        eng = A.engine()
        with eng.begin() as conn:
            resultado, motivo = chamadas.decidir(conn, caller, destino, datetime.now(TZ_SP))
    except Exception as e:
        A.agi_verbose(f'check_call: ERRO {e}')
        A.agi_set_variable('CALL_RESULT', 'BLOCK_ERROR')
        return
    A.agi_verbose(f'check_call: {resultado} {motivo or ""}')
    A.agi_set_variable('CALL_RESULT', resultado)
    if resultado == 'ALLOW' and motivo and motivo.startswith('PJSIP/'):
        dial, _, limite = motivo.partition(';limite=')   # 9/8+ID: celular da familia pelo tronco, com teto
        A.agi_set_variable('FAMILIA_DIAL', dial)
        A.agi_set_variable('FAMILIA_LIMITE_MS', str(int(limite or 1800) * 1000))


if __name__ == '__main__':
    main()
