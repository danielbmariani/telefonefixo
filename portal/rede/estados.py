"""
estados.py — Maquina de estados do telefone (doc 09, secao 2).

Toda mudanca de estado passa por transicionar(), que grava device_state_history
e audit_log na mesma transacao. Nenhum outro codigo escreve telefones.estado.
"""

from sqlalchemy import select, update

from . import db, auditoria
from .tempo import agora

ESTADOS = (
    'dados_informados', 'gdms_cadastrado', 'aguardando_boot', 'config_entregue',
    'registrado', 'ativo', 'erro_gdms_conflito', 'erro_dados', 'sem_boot',
    'sem_registro', 'desativado',
)

# (estado_atual, evento) -> novo_estado. None = criacao.
TRANSICOES = {
    (None, 'dados_informados'): 'dados_informados',
    ('erro_dados', 'dados_informados'): 'dados_informados',
    ('erro_gdms_conflito', 'dados_informados'): 'dados_informados',
    ('desativado', 'reativar'): 'dados_informados',

    ('dados_informados', 'gdms_ok'): 'gdms_cadastrado',
    ('dados_informados', 'gdms_conflito'): 'erro_gdms_conflito',
    ('dados_informados', 'gdms_dados_invalidos'): 'erro_dados',
    ('dados_informados', 'gdms_falha_persistente'): 'erro_dados',

    ('gdms_cadastrado', 'config_enviada'): 'aguardando_boot',

    ('aguardando_boot', 'config_entregue'): 'config_entregue',
    ('sem_boot', 'config_entregue'): 'config_entregue',
    ('sem_registro', 'config_entregue'): 'config_entregue',
    ('erro_dados', 'config_entregue'): 'config_entregue',   # kit chegou antes do GDMS? prova fisica vale

    ('config_entregue', 'sip_registrado'): 'registrado',
    ('sem_registro', 'sip_registrado'): 'registrado',

    ('registrado', 'primeira_chamada'): 'ativo',

    ('aguardando_boot', 'timeout_boot'): 'sem_boot',
    ('config_entregue', 'timeout_registro'): 'sem_registro',
}
EVENTOS_DESATIVAR = ('desativar', 'vinculo_expirado', 'troca_de_aparelho')
# Marcacoes de tempo por evento
CARIMBOS = {
    'gdms_ok': 'gdms_cadastrado_em', 'config_enviada': 'config_enviada_em',
    'config_entregue': 'config_entregue_em', 'sip_registrado': 'registrado_em',
    'primeira_chamada': 'ativo_em',
}


class TransicaoInvalida(Exception):
    pass


def estado_atual(conn, telefone_id):
    return conn.execute(select(db.telefones.c.estado).where(db.telefones.c.id == telefone_id)).scalar_one()


def proximo_estado(atual, evento):
    if evento in EVENTOS_DESATIVAR:
        return 'desativado'
    try:
        return TRANSICOES[(atual, evento)]
    except KeyError:
        raise TransicaoInvalida(f'{atual} + {evento}')


def transicionar(conn, telefone_id, evento, ator_tipo='sistema', ator_id=None, detalhes=None):
    """Aplica o evento. Retorna o novo estado. Levanta TransicaoInvalida."""
    atual = estado_atual(conn, telefone_id)
    novo = proximo_estado(atual, evento)
    valores = {'estado': novo}
    if evento in CARIMBOS:
        valores[CARIMBOS[evento]] = agora()
    if novo == 'desativado':
        valores['desativado_em'] = agora()
    conn.execute(update(db.telefones).where(db.telefones.c.id == telefone_id).values(**valores))
    aid = auditoria.registrar(conn, f'telefone_{evento}', ator_tipo, ator_id, 'telefone', telefone_id,
                              detalhes={'de': atual, 'para': novo, **(detalhes or {})})
    conn.execute(db.device_state_history.insert().values(
        ts=agora(), telefone_id=telefone_id, de=atual, para=novo, evento=evento,
        ator_tipo=ator_tipo, ator_id=None if ator_id is None else str(ator_id), audit_id=aid))
    return novo


def pode(atual, evento):
    try:
        proximo_estado(atual, evento)
        return True
    except TransicaoInvalida:
        return False
