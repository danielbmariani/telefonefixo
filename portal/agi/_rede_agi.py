"""
_rede_agi.py — base dos AGIs da rede aberta.

Os AGIs rodam como usuario asterisk, com o Python do venv do portal
(shebang #!/opt/rede-aberta/venv/bin/python3) e importam o pacote `rede`.
A URL do banco vem de /etc/rede-aberta/portal.env (REDE_DATABASE_URL).
"""

import os
import sys

PORTAL_DIR = os.environ.get('REDE_PORTAL_DIR', '/opt/rede-aberta/portal')
ENV_FILE = os.environ.get('REDE_ENV_FILE', '/etc/rede-aberta/portal.env')

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)


def carregar_env():
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith('#') or '=' not in linha:
                    continue
                k, v = linha.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def engine():
    carregar_env()
    from rede import db
    return db.criar_engine(os.environ.get('REDE_DATABASE_URL', 'sqlite:///rede-dev.db'))


def agi_read_env():
    env = {}
    while True:
        line = sys.stdin.readline().strip()
        if line == '':
            break
        if ':' in line:
            k, _, v = line.partition(':')
            env[k.strip()] = v.strip()
    return env


def agi_set_variable(name, value):
    sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
    sys.stdout.flush()
    sys.stdin.readline()


def agi_get_variable(name):
    sys.stdout.write(f'GET VARIABLE {name}\n')
    sys.stdout.flush()
    r = sys.stdin.readline().strip()
    if '(' in r and ')' in r:
        return r.split('(', 1)[1].rsplit(')', 1)[0]
    return ''


def agi_verbose(msg):
    sys.stdout.write(f'VERBOSE "{msg}" 3\n')
    sys.stdout.flush()
    sys.stdin.readline()


def caller_de(env):
    c = env.get('agi_callerid', '')
    if '<' in c and '>' in c:
        c = c.split('<')[1].split('>')[0]
    return c.strip('"').strip()
