#!/opt/rede-aberta/venv/bin/python3
"""log_call.py — AGI: registra a chamada com duracao em call_logs (hangup handler)."""

import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402


def main():
    env = A.agi_read_env()
    caller = A.caller_de(env)
    destino = A.agi_get_variable('CALL_DEST')
    dialstatus = A.agi_get_variable('DIALSTATUS')
    dur = A.agi_get_variable('CALL_DURATION')
    duracao = int(dur) if dur.isdigit() else None
    if dialstatus == 'ANSWER' or (duracao and duracao > 0):
        status = 'ALLOWED'
    elif dialstatus in ('BUSY', 'NOANSWER', 'CANCEL'):
        status = dialstatus
    else:
        status = 'ALLOWED'
    detalhe = A.agi_get_variable('GRUPO_DETALHE') if destino == 'GRUPO' else None
    try:
        from rede import db
        from rede.tempo import agora_sp_texto
        with A.engine().begin() as conn:
            conn.execute(db.call_logs.insert().values(caller_ext=caller, callee_ext=destino, timestamp=agora_sp_texto(),
                                                      status=status, duration_seconds=duracao, block_reason=detalhe or None))
    except Exception as e:
        A.agi_verbose(f'log_call: ERRO {e}')


if __name__ == '__main__':
    main()
