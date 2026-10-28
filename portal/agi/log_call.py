"""log_call.py — AGI: registra a chamada em call_logs (depois do Dial ou no hangup handler).

Status vem do DIALSTATUS do Asterisk; a duracao e o tempo atendido (ANSWEREDTIME), nao o tempo
total desde o inicio do Dial. Antes (ate 28/10/2026) qualquer chamada que tocou por 1 s ou mais era
gravada como ALLOWED com o tempo de toque incluido, e a aba Ligacoes dizia "Completada" para ligacao
que ninguem atendeu.
"""
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402

PERDIDAS = {'BUSY': 'BUSY', 'NOANSWER': 'NOANSWER', 'CANCEL': 'CANCEL', 'CHANUNAVAIL': 'NOANSWER',
            'CONGESTION': 'NOANSWER', 'DONTCALL': 'CANCEL', 'TORTURE': 'CANCEL', 'INVALIDARGS': 'NOANSWER'}


def classificar(dialstatus, answeredtime, duracao_total):
    """(status, duracao). ANSWER: ALLOWED com o tempo atendido (ou o total, se o Asterisk nao informou).
    Nao atendida: o status do Asterisk, sem duracao. Sem DIALSTATUS (o Dial nem rodou): ALLOWED se
    houve tempo, senao CANCEL."""
    def inteiro(v):
        return int(v) if isinstance(v, str) and v.isdigit() else (v if isinstance(v, int) else None)
    atendido, total = inteiro(answeredtime), inteiro(duracao_total)
    if dialstatus == 'ANSWER':
        return 'ALLOWED', atendido if atendido is not None else total
    if dialstatus in PERDIDAS:
        return PERDIDAS[dialstatus], None
    if atendido:
        return 'ALLOWED', atendido
    return ('ALLOWED', total) if total else ('CANCEL', None)


def main():
    env = A.agi_read_env()
    caller = A.caller_de(env)
    destino = A.agi_get_variable('CALL_DEST')
    status, duracao = classificar(A.agi_get_variable('DIALSTATUS'), A.agi_get_variable('ANSWEREDTIME'),
                                  A.agi_get_variable('CALL_DURATION'))
    try:
        from rede import db
        from rede.tempo import agora_sp_texto
        with A.engine().begin() as conn:
            conn.execute(db.call_logs.insert().values(caller_ext=caller, callee_ext=destino, timestamp=agora_sp_texto(),
                                                      status=status, duration_seconds=duracao))
    except Exception as e:  # noqa: BLE001
        A.agi_verbose(f'log_call: ERRO {e}')


if __name__ == '__main__':
    main()
