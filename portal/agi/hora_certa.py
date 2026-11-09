#!/opt/rede-aberta/venv/bin/python3
"""
hora_certa.py — AGI que fala a hora atual em portugues brasileiro (ramal 100).
Usa frases completas pre-gravadas em /usr/share/asterisk/sounds/hora/

Exemplo: 14:35 -> "quatorze horas" + "e trinta e cinco minutos"
         13:00 -> "treze horas"
         00:30 -> "zero hora" + "e meia"

A hora e a da casa da crianca que ligou (familias.fuso, rede/fusos.py). Se nao der para descobrir
(banco fora, ID desconhecido), fala a hora de Sao Paulo: a hora certa nunca fica muda.
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import _rede_agi as A  # noqa: E402

SOUND_DIR = 'hora'


def agi_exec(app, args=''):
    sys.stdout.write(f'EXEC {app} "{args}"\n')
    sys.stdout.flush()
    sys.stdin.readline()


def fuso_de(id_rede):
    """Fuso da familia da crianca (nome IANA) ou None = padrao."""
    try:
        from sqlalchemy import select
        from rede import db
        eng = A.engine()
        with eng.begin() as conn:
            return conn.execute(select(db.familias.c.fuso)
                                .select_from(db.criancas.join(db.familias, db.criancas.c.familia_id == db.familias.c.id))
                                .where(db.criancas.c.id_rede == id_rede)).scalar()
    except Exception as e:
        A.agi_verbose(f'hora_certa: sem fuso da familia ({type(e).__name__}), usando o padrao')
        return None


def main():
    env = A.agi_read_env()
    caller = A.caller_de(env)
    try:
        from rede.fusos import zona
        agora = datetime.now(timezone.utc).astimezone(zona(fuso_de(caller)))
    except Exception:
        import pytz
        agora = datetime.now(pytz.timezone('America/Sao_Paulo'))

    # Tocar a hora (ex: "quatorze horas")
    agi_exec('Playback', f'{SOUND_DIR}/h{agora.hour}')

    # Tocar os minutos se houver (ex: "e trinta e cinco minutos")
    if agora.minute > 0:
        agi_exec('Playback', f'{SOUND_DIR}/m{agora.minute}')


if __name__ == '__main__':
    main()
