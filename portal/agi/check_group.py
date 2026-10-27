#!/opt/rede-aberta/venv/bin/python3
"""check_group.py — AGI: caller precisa de amizade aceita com TODOS os membros da conferencia (CONF_MEMBERS)."""

import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402


def main():
    env = A.agi_read_env()
    caller = A.caller_de(env)
    membros = [m.strip() for m in A.agi_get_variable('CONF_MEMBERS').split(',') if m.strip()]
    if not membros:
        A.agi_set_variable('GROUP_RESULT', 'BLOCK')
        return
    try:
        from rede.servicos import chamadas
        with A.engine().begin() as conn:
            ok = chamadas.permitido_com_todos(conn, caller, membros)
    except Exception as e:
        A.agi_verbose(f'check_group: ERRO {e}')
        ok = False
    A.agi_set_variable('GROUP_RESULT', 'ALLOW' if ok else 'BLOCK')


if __name__ == '__main__':
    main()
