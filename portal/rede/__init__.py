"""
rede — Portal do Telefone Fixo (telefone fixo para criancas, caminho 3 / zero-touch).

create_app() monta o Flask com: banco (SQLAlchemy Core), auditoria por request,
blueprints web, comandos de linha (init-db, gdms-fila, jobs-rapidos, reconciliar,
exportar-auditoria, criar-operador).
"""

import uuid

import click
from flask import Flask, g, request, session, abort

from . import config as _config
from . import db as _db
from . import auditoria
from .email_envio import criar_mailer


# Scripts e estilos inline existem nos templates (polling, feedback de envio, horarios); por isso 'unsafe-inline'.
# Nenhum dado de usuario entra em <script> sem json.dumps, e o Jinja escapa o resto.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
       "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
       "font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")


def create_app(cfg=None):
    cfg = cfg or _config.Config()
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = cfg.SECRET_KEY
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = cfg.AMBIENTE == 'producao'
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
    from datetime import timedelta
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)   # sessao expira; renovada a cada request
    app.cfg = cfg
    app.engine = _db.criar_engine(cfg.DATABASE_URL)
    app.mailer = criar_mailer(cfg)

    # --- conexao e request_id por request ---
    @app.before_request
    def _antes():
        g.request_id = str(uuid.uuid4())
        g.ip = request.headers.get('X-Real-IP', request.remote_addr)
        g.user_agent = (request.headers.get('User-Agent') or '')[:300]
        if request.method == 'POST' and not request.path.startswith(('/p/', '/gdms/eventos/')):
            tok = session.get('_csrf_token')
            form_tok = request.form.get('_csrf_token')
            if not tok or not form_tok or tok != form_tok:
                abort(403)

    @app.after_request
    def _cabecalhos(resp):
        # Tambem definidos no nginx; aqui cobrem dev/testes e qualquer caminho que escape do proxy.
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'no-referrer')
        resp.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        resp.headers.setdefault('Content-Security-Policy', CSP)
        return resp

    @app.teardown_appcontext
    def _fim(exc):
        _db.fechar_conexao(exc)

    @app.context_processor
    def _globais():
        from .seguranca import gerar_csrf_token
        return {'csrf_token': gerar_csrf_token, 'cfg': cfg, 'nome_rede': cfg.NOME_REDE}

    from .web import filtros
    filtros.registrar(app)

    from .web.auth import bp as bp_auth
    from .web.familia import bp as bp_familia
    from .web.provisionamento import bp as bp_prov
    from .web.admin import bp as bp_admin
    from .web.gdms_eventos import bp as bp_gdms
    app.register_blueprint(bp_gdms)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_familia)
    app.register_blueprint(bp_prov)
    app.register_blueprint(bp_admin)

    _registrar_comandos(app)
    return app


def _registrar_comandos(app):
    from .servicos import gdms_fila, sip, reconciliacao, contas

    @app.cli.command('init-db')
    def init_db_cmd():
        """Cria as tabelas (nao recria as que ja existem)."""
        _db.init_db(app.engine)
        click.echo('tabelas criadas')

    @app.cli.command('criar-operador')
    @click.argument('email')
    @click.argument('senha')
    @click.option('--nome', default='Operador ONG')
    @click.option('--papel', default='operador', type=click.Choice(['operador', 'admin']))
    def criar_operador_cmd(email, senha, nome, papel):
        """Cria uma conta de operador/admin da ONG (ja verificada)."""
        with app.engine.begin() as conn:
            fid = contas.criar_operador(conn, email, senha, nome, papel)
        click.echo(f'operador criado: id={fid}')

    @app.cli.command('gdms-fila')
    def gdms_fila_cmd():
        """Processa a fila de cadastro no GDMS (rodar a cada minuto)."""
        with app.engine.begin() as conn:
            n = gdms_fila.processar(conn, app.cfg)
        click.echo(f'processados: {n}')

    @app.cli.command('gdms-eventos')
    def gdms_eventos_cmd():
        """Registra no GDMS a URL do webhook (SITE_URL/gdms/eventos/<segredo>) e assina os eventos da org."""
        from .servicos import gdms_eventos
        with app.engine.begin() as conn:
            cli = gdms_fila.criar_cliente(app.cfg, conn)
            cli.obter_token(app.cfg.GDMS_USERNAME, app.cfg.GDMS_PASSWORD)
            r1, r2 = gdms_eventos.registrar_assinatura(cli, app.cfg)
        click.echo(f'callback/set_url: {r1}')
        click.echo(f'subscribe/save: {r2}')

    @app.cli.command('gdms-xml')
    @click.argument('telefone_id', type=int)
    def gdms_xml_cmd(telefone_id):
        """Imprime o XML que o GDMS entregaria ao telefone (para carregar a mao na tarefa manual)."""
        from .servicos import telefones
        with app.engine.begin() as conn:
            tel = telefones.por_id(conn, telefone_id)
            if not tel:
                raise click.ClickException('telefone inexistente')
            click.echo(telefones.gerar_xml_gdms(conn, tel, app.cfg), nl=False)

    @app.cli.command('gdms-reenviar-config')
    @click.argument('telefone_id', type=int)
    def gdms_reenviar_config_cmd(telefone_id):
        """Reenvia pela API do GDMS o XML ponteiro de um telefone ja cadastrado (ex.: travas novas)."""
        from .servicos import telefones, gdms_fila
        with app.engine.begin() as conn:
            tel = telefones.por_id(conn, telefone_id)
            if not tel:
                raise click.ClickException('telefone inexistente')
            gdms_fila.reenviar_config(conn, telefone_id)
        click.echo('enfileirado; a fila do minuto envia')

    @app.cli.command('gdms-teclas')
    @click.argument('crianca_id', type=int)
    def gdms_teclas_cmd(crianca_id):
        """Reenvia pelo GDMS as teclas de discagem rapida do telefone desta crianca."""
        from .servicos import gdms_fila
        with app.engine.begin() as conn:
            ok = gdms_fila.atualizar_teclas(conn, crianca_id)
        click.echo('enfileirado; a fila do minuto envia' if ok else 'crianca sem telefone no GDMS')

    @app.cli.command('jobs-rapidos')
    def jobs_rapidos_cmd():
        """Observa registros SIP e aplica timeouts (rodar a cada minuto)."""
        with app.engine.begin() as conn:
            r = sip.observar(conn, app.cfg)
            from .servicos import custos
            r['alertas_teto'] = custos.verificar_alertas(conn, app.cfg, app.mailer)
        click.echo(str(r))

    @app.cli.command('reconciliar')
    def reconciliar_cmd():
        """Reconciliacoes diarias (banco x Asterisk x GDMS x estados)."""
        gdms_macs = None
        if app.cfg.GDMS_MODO == 'real':
            try:
                with app.engine.begin() as conn:
                    cli = gdms_fila.criar_cliente(app.cfg, conn)
                    cli.obter_token(app.cfg.GDMS_USERNAME, app.cfg.GDMS_PASSWORD)
                    gdms_macs = cli.macs_da_organizacao(app.cfg.GDMS_ORG_ID)
            except Exception as e:
                click.echo(f'aviso: nao foi possivel listar o GDMS ({e}); reconciliacao GDMS x banco pulada')
        with app.engine.begin() as conn:
            r = reconciliacao.executar(conn, app.cfg, gdms_macs=gdms_macs)
            from .servicos import retencao
            r['retencao'] = retencao.aplicar(conn, app.cfg)
        click.echo(str(r))

    @app.cli.command('exportar-auditoria')
    @click.option('--dia', default=None, help='YYYY-MM-DD (padrao: ontem)')
    @click.option('--destino', default='/var/backups/rede-aberta/auditoria')
    def exportar_cmd(dia, destino):
        """Exporta o audit_log de um dia em CSV com SHA-256."""
        with app.engine.begin() as conn:
            r = reconciliacao.exportar_auditoria(conn, dia, destino)
        click.echo(str(r))
