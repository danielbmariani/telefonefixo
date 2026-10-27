"""
db.py — Esquema (SQLAlchemy Core) e conexao por request.

Tabelas de negocio em portugues. Tabelas que o Asterisk le (ps_*) e a de
chamadas (call_logs) mantem os nomes do projeto atual para reaproveitar AGIs.
Tabelas de auditoria (audit_log, device_state_history, prov_log, gdms_log) sao
append-only: em producao o papel do portal nao tem UPDATE/DELETE nelas
(deploy/grants.sql).
"""

from flask import g, current_app
from sqlalchemy import (
    MetaData, Table, Column, Integer, Text, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index, create_engine, event, text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
JSONT = JSON().with_variant(JSONB, 'postgresql')


def _ts(nome, **kw):
    return Column(nome, DateTime(timezone=True), **kw)


# --- Contas e consentimento -------------------------------------------------

familias = Table('familias', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('email', Text, nullable=False, unique=True),
    Column('senha_hash', Text, nullable=False),
    Column('nome', Text, nullable=False, default=''),
    Column('papel', Text, nullable=False, default='familia'),   # familia | operador | admin
    _ts('verificado_em'),
    _ts('criado_em', nullable=False),
    Column('suspensa', Boolean, nullable=False, default=False),
)

verificacoes_email = Table('verificacoes_email', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('email', Text, nullable=False),
    Column('senha_hash', Text, nullable=False),
    Column('nome', Text, nullable=False, default=''),
    Column('codigo', Text, nullable=False),
    Column('tentativas', Integer, nullable=False, default=0),
    _ts('expira_em', nullable=False),
    _ts('criado_em', nullable=False),
    Column('ip', Text),
    Column('usado', Boolean, nullable=False, default=False),
)

consentimentos = Table('consentimentos', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('familia_id', Integer, ForeignKey('familias.id'), nullable=False),
    Column('tipo', Text, nullable=False),            # termos | privacidade | crianca
    Column('versao', Text, nullable=False),
    Column('hash_texto', Text, nullable=False),
    _ts('ts', nullable=False),
    Column('ip', Text),
)

password_resets = Table('password_resets', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('email', Text, nullable=False),
    Column('token_hash', Text, nullable=False, unique=True),
    _ts('criado_em', nullable=False),
    Column('usado', Boolean, nullable=False, default=False),
)

# --- Criancas e telefones ---------------------------------------------------

criancas = Table('criancas', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('familia_id', Integer, ForeignKey('familias.id'), nullable=False),
    Column('apelido', Text, nullable=False, unique=True),
    Column('id_rede', Text, nullable=False, unique=True),     # 6 digitos, [2-7]XXXXX
    Column('senha_sip', Text, nullable=False),                # o Asterisk precisa dela em claro (ps_auths)
    _ts('criado_em', nullable=False),
    Column('ativa', Boolean, nullable=False, default=True),
    _ts('nao_perturbe_ate'),                                  # 'silenciar agora' ate este instante (item 3 do doc 12)
    _ts('desativada_em'),
)

telefones = Table('telefones', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('crianca_id', Integer, ForeignKey('criancas.id'), nullable=False),
    Column('mac', Text, nullable=False),                      # 12 hex maiusculos
    Column('serial', Text, nullable=False),
    Column('modelo', Text, nullable=False, default='grp'),
    Column('estado', Text, nullable=False),
    Column('admin_senha', Text, nullable=False),              # senha admin gravada no aparelho via XML
    Column('xml_versao', Integer, nullable=False, default=1),
    _ts('informado_em', nullable=False),
    _ts('gdms_cadastrado_em'),
    _ts('config_enviada_em'),
    _ts('gdms_online_em'),          # ultimo evento deviceStatus=1 recebido do GDMS (webhook)
    _ts('gdms_conta_up_em'),        # ultimo evento accountStatus=Up recebido do GDMS (webhook)
    _ts('familia_ligou_em'),
    _ts('config_entregue_em'),
    _ts('registrado_em'),
    _ts('ativo_em'),
    _ts('desativado_em'),
    _ts('ultimo_prov_em'),
    Column('ultimo_prov_ip', Text),
    Column('ultimo_prov_ua', Text),
    _ts('ultimo_sip_em'),
    Column('ultimo_sip_ip', Text),
    Column('ultimo_sip_ua', Text),
    Column('loja', Text),
    Column('observacao', Text),
)
Index('telefones_mac', telefones.c.mac)
Index('telefones_estado', telefones.c.estado)

# Celulares da familia: destino do 9+ID (a crianca liga para a familia) e origem autorizada da entrada
# pelo tronco (a familia liga para a crianca). Numero nacional so digitos: DDD + numero (10 ou 11).
familia_telefones = Table('familia_telefones', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('familia_id', Integer, ForeignKey('familias.id', ondelete='CASCADE'), nullable=False),
    Column('numero', Text, nullable=False),
    Column('apelido', Text, nullable=False, default=''),      # 'Mae', 'Pai', 'Casa da vo'
    Column('posicao', Integer),                               # 1 = disca 9+ID, 2 = disca 8+ID
    Column('ativo', Boolean, nullable=False, default=True),
    _ts('criado_em', nullable=False),
    _ts('verificado_em'),                                     # reservado: confirmacao por ligacao/SMS
    UniqueConstraint('familia_id', 'numero', name='familia_telefones_unico'),
)
Index('familia_telefones_numero', familia_telefones.c.numero)

# Avisos de teto ja enviados (um por crianca/mes/nivel e um por dia da rede), para nao repetir e-mail.
alertas_custo = Table('alertas_custo', metadata,
    Column('chave', Text, primary_key=True),
    _ts('ts', nullable=False),
)

prov_tokens = Table('prov_tokens', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('telefone_id', Integer, ForeignKey('telefones.id'), nullable=False),
    Column('token', Text, nullable=False, unique=True),       # vai na URL do P237; mesma classe de segredo que senha_sip
    Column('ativo', Boolean, nullable=False, default=True),
    _ts('criado_em', nullable=False),
    _ts('revogado_em'),
    Column('motivo_revogacao', Text),
)

gdms_fila = Table('gdms_fila', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('telefone_id', Integer, ForeignKey('telefones.id'), nullable=False),
    Column('estado', Text, nullable=False, default='pendente'),   # pendente | ok | erro | cancelada
    Column('etapa', Text, nullable=False, default='cadastro'),    # cadastro (device/add) | config (device/config/xml)
    Column('tentativas', Integer, nullable=False, default=0),
    _ts('proxima_em', nullable=False),
    Column('ultimo_ret_code', Integer),
    Column('ultima_msg', Text),
    _ts('criado_em', nullable=False),
    _ts('atualizado_em'),
)

tarefas = Table('tarefas', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('tipo', Text, nullable=False),                     # enviar_config_gdms | remover_gdms | ...
    Column('telefone_id', Integer, ForeignKey('telefones.id')),
    Column('descricao', Text, nullable=False),
    Column('estado', Text, nullable=False, default='aberta'),  # aberta | concluida | cancelada
    _ts('criado_em', nullable=False),
    _ts('concluido_em'),
    Column('concluido_por', Text),
    Column('motivo', Text),
)

casos = Table('casos', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('tipo', Text, nullable=False),
    Column('gravidade', Text, nullable=False, default='media'),  # baixa | media | alta
    Column('telefone_id', Integer, ForeignKey('telefones.id')),
    Column('crianca_id', Integer, ForeignKey('criancas.id')),
    Column('familia_id', Integer, ForeignKey('familias.id')),
    Column('descricao', Text, nullable=False),
    Column('detalhes', JSONT),
    Column('estado', Text, nullable=False, default='aberto'),  # aberto | resolvido
    _ts('criado_em', nullable=False),
    _ts('resolvido_em'),
    Column('resolvido_por', Text),
    Column('motivo', Text),
)

# --- Amizades, horarios, chamadas -------------------------------------------

amizades = Table('amizades', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('de_crianca_id', Integer, ForeignKey('criancas.id'), nullable=False),
    Column('para_crianca_id', Integer, ForeignKey('criancas.id'), nullable=False),
    Column('estado', Text, nullable=False, default='pendente'),  # pendente | aceita | recusada | bloqueada | removida
    _ts('criado_em', nullable=False),
    _ts('respondido_em'),
    Column('recusas', Integer, nullable=False, default=0),
    Column('mensagem', Text),                                   # quem pede se apresenta: 'Joao, 4a serie da Escola X' (ate 80 chars)
    UniqueConstraint('de_crianca_id', 'para_crianca_id', name='amizades_par'),
)

# Turma: grupo de criancas (escola, predio, time). Quem cria administra; quem entra pelo codigo
# espera o aceite do administrador; ao entrar, a crianca pede amizade a todos os membros, e cada
# familia continua aceitando um a um (doc 12, item 1).
turmas = Table('turmas', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('nome', Text, nullable=False),
    Column('codigo', Text, nullable=False, unique=True),       # 6 caracteres sem I/O/0/1
    Column('familia_id', Integer, ForeignKey('familias.id'), nullable=False),   # administradora
    Column('ativa', Boolean, nullable=False, default=True),
    _ts('criado_em', nullable=False),
)

turma_membros = Table('turma_membros', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('turma_id', Integer, ForeignKey('turmas.id'), nullable=False),
    Column('crianca_id', Integer, ForeignKey('criancas.id'), nullable=False),
    Column('estado', Text, nullable=False, default='pendente'),  # pendente | aceita | recusada | saiu
    _ts('criado_em', nullable=False),
    _ts('respondido_em'),
    UniqueConstraint('turma_id', 'crianca_id', name='turma_membro_unico'),
)

horarios = Table('horarios', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('crianca_id', Integer, ForeignKey('criancas.id', ondelete='CASCADE'), nullable=False),
    Column('dia_semana', Integer, nullable=False),            # 0=segunda ... 6=domingo
    Column('inicio', Text, nullable=False),                   # HH:MM
    Column('fim', Text, nullable=False),
    UniqueConstraint('crianca_id', 'dia_semana', name='horarios_dia'),
)

call_logs = Table('call_logs', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('caller_ext', Text, nullable=False),
    Column('callee_ext', Text, nullable=False),
    Column('timestamp', Text, nullable=False),                # 'YYYY-MM-DD HH:MM:SS' em Sao Paulo (como hoje)
    Column('status', Text, nullable=False),
    Column('duration_seconds', Integer),
    Column('block_reason', Text),
)
Index('call_logs_caller', call_logs.c.caller_ext)
Index('call_logs_callee', call_logs.c.callee_ext)

# Retencao (doc 13): depois de RETENCAO_CHAMADAS_DIAS, as linhas de call_logs viram so totais por dia.
chamadas_resumo = Table('chamadas_resumo', metadata,
    Column('dia', Text, primary_key=True),                    # 'YYYY-MM-DD' em Sao Paulo
    Column('chamadas', Integer, nullable=False, default=0),
    Column('segundos', Integer, nullable=False, default=0),
    Column('bloqueadas', Integer, nullable=False, default=0),
)

# --- Auditoria (append-only) ------------------------------------------------

audit_log = Table('audit_log', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _ts('ts', nullable=False),
    Column('request_id', Text, nullable=False),
    Column('ator_tipo', Text, nullable=False),                # familia | sistema | operador | telefone
    Column('ator_id', Text),
    Column('acao', Text, nullable=False),
    Column('objeto_tipo', Text),
    Column('objeto_id', Text),
    Column('ip', Text),
    Column('user_agent', Text),
    Column('detalhes', JSONT),
    Column('corrige_id', Integer, ForeignKey('audit_log.id')),
)
Index('audit_log_objeto', audit_log.c.objeto_tipo, audit_log.c.objeto_id, audit_log.c.ts)
Index('audit_log_req', audit_log.c.request_id)
Index('audit_log_acao', audit_log.c.acao, audit_log.c.ts)

device_state_history = Table('device_state_history', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _ts('ts', nullable=False),
    Column('telefone_id', Integer, nullable=False),
    Column('de', Text),
    Column('para', Text, nullable=False),
    Column('evento', Text, nullable=False),
    Column('ator_tipo', Text, nullable=False),
    Column('ator_id', Text),
    Column('audit_id', Integer, ForeignKey('audit_log.id')),
)
Index('dsh_telefone', device_state_history.c.telefone_id, device_state_history.c.ts)

prov_log = Table('prov_log', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _ts('ts', nullable=False),
    Column('ip', Text),
    Column('user_agent', Text),
    Column('mac_pedido', Text),
    Column('token_id', Integer),
    Column('telefone_id', Integer),
    Column('resultado', Text, nullable=False),   # entregue | token_invalido | mac_nao_bate | estado_invalido | rate_limit
    Column('xml_versao', Integer),
    Column('xml_sha256', Text),
    Column('request_id', Text),
)
Index('prov_log_mac', prov_log.c.mac_pedido, prov_log.c.ts)

gdms_log = Table('gdms_log', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _ts('ts', nullable=False),
    Column('request_id', Text),
    Column('telefone_id', Integer),
    Column('endpoint', Text, nullable=False),
    Column('metodo', Text, nullable=False),
    Column('corpo_enviado', JSONT),
    Column('http_status', Integer),
    Column('ret_code', Integer),
    Column('msg', Text),
    Column('corpo_resposta', JSONT),
    Column('latencia_ms', Integer),
    Column('tentativa', Integer, nullable=False, default=1),
)

# --- Asterisk realtime (subconjunto; em producao o alembic do Asterisk cria
# estas tabelas antes, com todas as colunas; create_all pula as existentes) ---

ps_endpoints = Table('ps_endpoints', metadata,
    Column('id', Text, primary_key=True),
    Column('transport', Text), Column('aors', Text), Column('auth', Text),
    Column('context', Text), Column('disallow', Text), Column('allow', Text),
    Column('direct_media', Text), Column('rtp_symmetric', Text), Column('force_rport', Text),
    Column('rewrite_contact', Text), Column('callerid', Text), Column('dtmf_mode', Text),
)
ps_auths = Table('ps_auths', metadata,
    Column('id', Text, primary_key=True),
    Column('auth_type', Text), Column('username', Text), Column('password', Text),
)
ps_aors = Table('ps_aors', metadata,
    Column('id', Text, primary_key=True),
    Column('max_contacts', Integer), Column('remove_existing', Text),
    Column('default_expiration', Integer), Column('qualify_frequency', Integer),
)

# ps_contacts e escrita pelo Asterisk (muitas colunas). O portal so le.
# Fica em metadata separado para create_all NAO cria-la em producao.
metadata_asterisk = MetaData()
ps_contacts = Table('ps_contacts', metadata_asterisk,
    Column('id', Text, primary_key=True),
    Column('uri', Text), Column('expiration_time', Text), Column('user_agent', Text),
    Column('via_addr', Text), Column('via_port', Integer), Column('endpoint', Text),
    Column('reg_server', Text),
)


# --- Engine e conexao -------------------------------------------------------

def criar_engine(url):
    kw = {'future': True}
    if url.startswith('sqlite'):
        kw['connect_args'] = {'check_same_thread': False, 'timeout': 10}
    engine = create_engine(url, **kw)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def _pragmas(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute('PRAGMA foreign_keys=ON')
            cur.execute('PRAGMA journal_mode=WAL')
            cur.close()
    return engine


def init_db(engine, com_ps_contacts=False):
    metadata.create_all(engine, checkfirst=True)
    if com_ps_contacts:
        metadata_asterisk.create_all(engine, checkfirst=True)
    migrar(engine)


def migrar(engine):
    """Acrescenta colunas que existem no modelo e faltam no banco (ADD COLUMN, so colunas anulaveis).
    Suficiente para a evolucao do portal; nunca apaga nem muda tipo. Retorna [(tabela, coluna)]."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    feitas = []
    with engine.begin() as conn:
        for tabela in metadata.sorted_tables:
            if not insp.has_table(tabela.name):
                continue
            existentes = {c['name'] for c in insp.get_columns(tabela.name)}
            for col in tabela.columns:
                if col.name in existentes:
                    continue
                if not col.nullable and col.default is None and col.server_default is None:
                    raise RuntimeError(f'{tabela.name}.{col.name}: coluna NOT NULL nova precisa de migracao manual')
                tipo = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {tabela.name} ADD COLUMN {col.name} {tipo}'))
                feitas.append((tabela.name, col.name))
    return feitas


def tabela_existe(conn, nome):
    from sqlalchemy import inspect
    return inspect(conn).has_table(nome)


def conexao():
    """Conexao + transacao por request. Commit no teardown se nao houve excecao."""
    if 'conn' not in g:
        g.conn = current_app.engine.connect()
        g.trans = g.conn.begin()
    return g.conn


def fechar_conexao(exc):
    conn = g.pop('conn', None)
    trans = g.pop('trans', None)
    if conn is None:
        return
    try:
        if trans is not None and trans.is_active:
            if exc is None and not g.get('rollback'):
                trans.commit()
            else:
                trans.rollback()
    finally:
        conn.close()


def marcar_rollback():
    g.rollback = True
