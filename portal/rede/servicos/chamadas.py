"""
chamadas.py — Decisao de chamada usada pelo AGI check_call.py (e testavel sem Asterisk).

decidir(conn, caller, discado, agora_sp) -> (resultado, motivo)
  resultado: 'ALLOW' | 'BLOCK_UNKNOWN' | 'BLOCK_SCHEDULE_CALLER' | 'BLOCK_SCHEDULE_DEST'
             | 'BLOCK_PERMISSION' | 'BLOCK_PARENT' | 'BLOCK_TETO' | 'BLOCK_EXTERNO' | 'BLOCK_AMBIGUO' | 'BLOCK_ERROR'
  motivo: texto do bloqueio, ou None. Para ligacao pelo tronco (9/8+ID ou telefone da lista, doc 20), motivo e
          a string do Dial() seguida de ';limite=<segundos>' (teto da fase de teste), ';vono=<0|1>' e, para
          telefone da lista, ';dest=<numero>' (o que vai para call_logs no lugar do que foi discado). O AGI
          passa tudo ao dialplan em FAMILIA_DIAL, FAMILIA_LIMITE_MS, FAMILIA_VONO e FAMILIA_DEST.
"""

from sqlalchemy import insert

from .. import db, ids, ddd as svc_ddd
from .contas import _cfg
from ..tempo import agora_sp_texto
from . import amizades, horarios, criancas as svc_cri, familia_telefones as svc_fam, custos

BYPASS = {'100'}


def registrar_bloqueio(conn, caller, dest, motivo):
    conn.execute(insert(db.call_logs).values(caller_ext=caller, callee_ext=dest, timestamp=agora_sp_texto(),
                                             status='BLOCKED', block_reason=motivo))


def decidir(conn, caller, destino, agora_sp):
    tipo, alvo = ids.classificar_discado(destino)
    if tipo == 'servico' and destino in BYPASS:
        return 'ALLOW', None
    if tipo in ('familia1', 'familia2'):
        return decidir_familia(conn, caller, destino, alvo, agora_sp)
    if tipo in ('externo', 'externo_local'):
        return decidir_externo(conn, caller, destino, tipo, alvo, agora_sp)
    if tipo != 'crianca':
        registrar_bloqueio(conn, caller, destino, 'UNKNOWN_DEST')
        return 'BLOCK_UNKNOWN', 'UNKNOWN_DEST'
    dest_id = alvo
    quem = svc_cri.por_id_rede(conn, caller)
    if not quem or not quem['ativa']:
        registrar_bloqueio(conn, caller, dest_id, 'CALLER_NOT_ACTIVATED')
        return 'BLOCK_UNKNOWN', 'CALLER_NOT_ACTIVATED'
    para = svc_cri.por_id_rede(conn, dest_id)
    if not para or not para['ativa']:
        registrar_bloqueio(conn, caller, dest_id, 'UNKNOWN_DEST')
        return 'BLOCK_UNKNOWN', 'UNKNOWN_DEST'
    if not horarios.dentro_do_horario(conn, caller, agora_sp):
        registrar_bloqueio(conn, caller, dest_id, 'SCHEDULE_CALLER')
        return 'BLOCK_SCHEDULE_CALLER', 'SCHEDULE_CALLER'
    if not horarios.dentro_do_horario(conn, dest_id, agora_sp):
        registrar_bloqueio(conn, caller, dest_id, 'SCHEDULE_DEST')
        return 'BLOCK_SCHEDULE_DEST', 'SCHEDULE_DEST'
    if not amizades.permitido(conn, caller, dest_id):
        registrar_bloqueio(conn, caller, dest_id, 'PERMISSION')
        return 'BLOCK_PERMISSION', 'PERMISSION'
    return 'ALLOW', None


def _saida_pelo_tronco(conn, caller, destino, numero, agora_sp, extra=''):
    """Parte comum das ligacoes para fora: horario da crianca, teto de minutos, Vono disponivel."""
    if not horarios.dentro_do_horario(conn, caller, agora_sp):
        registrar_bloqueio(conn, caller, destino, 'SCHEDULE_CALLER')
        return 'BLOCK_SCHEDULE_CALLER', 'SCHEDULE_CALLER'
    segundos = custos.segundos_permitidos(conn, _cfg(), caller, 'saida', agora_sp)
    if segundos <= 0:
        registrar_bloqueio(conn, caller, destino, 'TETO')
        return 'BLOCK_TETO', 'TETO'
    vono = 1 if custos.vono_disponivel(conn, _cfg(), agora_sp) else 0
    return 'ALLOW', f'{svc_fam.dial_saida(numero)};limite={segundos};vono={vono}{extra}'


def decidir_familia(conn, caller, destino, alvo, agora_sp):
    """9+ID: celular 1 da propria familia; 8+ID: celular 2. So o proprio ID: 9 + ID de um amigo nao
    liga para a familia do amigo."""
    quem = svc_cri.por_id_rede(conn, caller)
    if not quem or not quem['ativa']:
        registrar_bloqueio(conn, caller, destino, 'CALLER_NOT_ACTIVATED')
        return 'BLOCK_UNKNOWN', 'CALLER_NOT_ACTIVATED'
    if alvo != caller:
        registrar_bloqueio(conn, caller, destino, 'FAMILIA_SO_PROPRIA')
        return 'BLOCK_PERMISSION', 'FAMILIA_SO_PROPRIA'
    numero = svc_fam.numero_por_prefixo(conn, quem, destino[0])
    if not numero:
        registrar_bloqueio(conn, caller, destino, 'FAMILIA_NAO_CONFIGURADA')
        return 'BLOCK_PARENT', 'FAMILIA_NAO_CONFIGURADA'
    return _saida_pelo_tronco(conn, caller, destino, numero, agora_sp)


def decidir_externo(conn, caller, destino, tipo, digitos, agora_sp):
    """Telefone da lista da familia (doc 20): a crianca discou o numero (do DDD da casa) ou DDD + numero.
    So completa o que a familia cadastrou; a central casa pelo fim do numero, e o DDD da casa desempata."""
    quem = svc_cri.por_id_rede(conn, caller)
    if not quem or not quem['ativa']:
        registrar_bloqueio(conn, caller, destino, 'CALLER_NOT_ACTIVATED')
        return 'BLOCK_UNKNOWN', 'CALLER_NOT_ACTIVATED'
    if _cfg().MAX_OUTROS <= 0:
        registrar_bloqueio(conn, caller, destino, 'EXTERNO_DESLIGADO')
        return 'BLOCK_UNKNOWN', 'EXTERNO_DESLIGADO'
    ddd_casa = svc_ddd.ddd_da_familia(conn, quem['familia_id'])
    numero, motivo = svc_fam.casar_discado(conn, quem['familia_id'], tipo, digitos, ddd_casa)
    if not numero:
        registrar_bloqueio(conn, caller, destino, motivo)
        return ('BLOCK_AMBIGUO' if motivo == 'EXTERNO_AMBIGUO' else 'BLOCK_EXTERNO'), motivo
    return _saida_pelo_tronco(conn, caller, destino, numero, agora_sp, extra=f';dest={numero}')
