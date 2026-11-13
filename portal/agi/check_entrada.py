#!/opt/rede-aberta/venv/bin/python3
"""check_entrada.py — AGI: ligacao chegando pelo tronco da operadora (telefone da lista -> crianca).
Logica em rede/servicos/familia_telefones.decidir_entrada (testada sem Asterisk). Fail-closed.
Define ENTRADA_RESULT e, se ALLOW, ENTRADA_DIAL, ENTRADA_DEST, ENTRADA_NOME, ENTRADA_NUMERO, ENTRADA_LIMITE_MS.
Se MENU (o mesmo numero em mais de uma familia, doc 20), ENTRADA_OPCOES (IDs separados por virgula),
ENTRADA_SONS (audio de cada opcao: nomes/<id> ou apelidos/<id>), ENTRADA_NOMES (nomes separados por ~) e
ENTRADA_LIMITES (ms separados por virgula); o dialplan pergunta e toca."""

import sys
from datetime import datetime

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402


def _limpo(texto):
    return ''.join(ch for ch in (texto or '') if ch not in ',~"\\')


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
    A.agi_verbose(f'check_entrada: {resultado} ids={dados.get("ids") or [o["id_rede"] for o in dados.get("opcoes", [])]}')
    A.agi_set_variable('ENTRADA_RESULT', resultado)
    A.agi_set_variable('ENTRADA_NUMERO', dados.get('numero', ''))
    if resultado == 'ALLOW':
        A.agi_set_variable('ENTRADA_DIAL', dados['dial'])
        A.agi_set_variable('ENTRADA_DEST', dados['ids'][0])
        A.agi_set_variable('ENTRADA_NOME', dados['nome'])
        A.agi_set_variable('ENTRADA_LIMITE_MS', str(int(dados.get('limite_s') or 1800) * 1000))
    elif resultado == 'MENU':
        ops = dados['opcoes']
        A.agi_set_variable('ENTRADA_OPCOES', ','.join(o['id_rede'] for o in ops))
        A.agi_set_variable('ENTRADA_SONS', ','.join(o.get('som') or f"apelidos/{o['id_rede']}" for o in ops))
        A.agi_set_variable('ENTRADA_NOMES', '~'.join(_limpo(o['nome']) for o in ops))
        A.agi_set_variable('ENTRADA_LIMITES', ','.join(str(int(o.get('limite_s') or 1800) * 1000) for o in ops))


if __name__ == '__main__':
    main()
