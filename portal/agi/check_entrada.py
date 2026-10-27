#!/opt/rede-aberta/venv/bin/python3
"""check_entrada.py — AGI: ligacao chegando pelo tronco da operadora (celular da familia -> crianca).
Logica em rede/servicos/familia_telefones.decidir_entrada (testada sem Asterisk). Fail-closed.
Define ENTRADA_RESULT e, se ALLOW, ENTRADA_DIAL, ENTRADA_DEST, ENTRADA_NOME, ENTRADA_NUMERO."""

import sys
from datetime import datetime

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402


def main():
    env = A.agi_read_env()
    identificador = A.caller_de(env)
    # args do dialplan: CALLERID(name), P-Asserted-Identity, Remote-Party-ID (a operadora pode por o
    # numero do chamador em qualquer um deles; o From user costuma ser o nosso proprio usuario do tronco)
    outros = [env.get(f'agi_arg_{i}', '') for i in (1, 2, 3)]
    A.agi_verbose(f'check_entrada: de={identificador} outros={outros} para={env.get("agi_extension", "")}')
    try:
        from rede.servicos import familia_telefones
        from rede.tempo import TZ_SP
        with A.engine().begin() as conn:
            resultado, dados = familia_telefones.decidir_entrada(conn, identificador, datetime.now(TZ_SP), *outros)
    except Exception as e:
        A.agi_verbose(f'check_entrada: ERRO {e}')
        A.agi_set_variable('ENTRADA_RESULT', 'BLOCK_ERROR')
        return
    A.agi_verbose(f'check_entrada: {resultado} ids={dados.get("ids")}')
    A.agi_set_variable('ENTRADA_RESULT', resultado)
    A.agi_set_variable('ENTRADA_NUMERO', dados.get('numero', ''))
    if resultado == 'ALLOW':
        A.agi_set_variable('ENTRADA_DIAL', dados['dial'])
        A.agi_set_variable('ENTRADA_DEST', dados['ids'][0])
        A.agi_set_variable('ENTRADA_NOME', dados['nome'])
        A.agi_set_variable('ENTRADA_LIMITE_MS', str(int(dados.get('limite_s') or 1800) * 1000))


if __name__ == '__main__':
    main()
