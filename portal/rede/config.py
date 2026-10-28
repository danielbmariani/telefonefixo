"""config.py — Toda configuracao vem de variaveis de ambiente REDE_*.
Em producao, o systemd le /etc/rede-aberta/portal.env (EnvironmentFile)."""

import os
import secrets


class Config:
    def __init__(self, env=None, **sobrescritas):
        e = dict(os.environ if env is None else env)
        e.update({f'REDE_{k}': str(v) for k, v in sobrescritas.items()})
        g = e.get

        self.AMBIENTE = g('REDE_AMBIENTE', 'dev')                      # dev | teste | producao
        self.NOME_REDE = g('REDE_NOME', 'Telefone Fixo')
        self.SECRET_KEY = g('REDE_SECRET_KEY') or secrets.token_hex(32)
        self.DATABASE_URL = g('REDE_DATABASE_URL', 'sqlite:///rede-dev.db')
        self.SITE_URL = g('REDE_SITE_URL', 'http://localhost:5000').rstrip('/')
        # Base publica do servidor de provisionamento (o telefone acessa). Pode ser o proprio site.
        self.PROV_URL = g('REDE_PROV_URL', self.SITE_URL).rstrip('/')
        self.SIP_HOST = g('REDE_SIP_HOST', '127.0.0.1')                # IP/host que vai no P47
        self.TIMEZONE = g('REDE_TIMEZONE', 'America/Sao_Paulo')
        # Tronco da operadora (B23): numero fixo da rede que a familia liga para alcancar a crianca. So digitos.
        self.TRONCO_NUMERO = g('REDE_TRONCO_NUMERO', '')
        # Voz sintetica (doc 16): frases fixas, apelidos e nomes de grupo em wav para o Asterisk.
        # VOZ_BACKEND: auto (piper se houver, senao espeak-ng), piper, espeak, nenhum (testes).
        self.VOZ_BACKEND = g('REDE_VOZ_BACKEND', 'nenhum')
        self.VOZ_DIR = g('REDE_VOZ_DIR', '/var/lib/rede-aberta/sons')
        self.VOZ_PIPER_MODELO = g('REDE_VOZ_PIPER_MODELO', '/opt/rede-aberta/piper/pt_BR-faber-medium.onnx')
        # ARI (servico rede-grupo): controla a chamada em grupo
        self.ARI_URL = g('REDE_ARI_URL', 'http://127.0.0.1:8088/ari')
        self.ARI_USUARIO = g('REDE_ARI_USUARIO', 'rede')
        self.ARI_SENHA = g('REDE_ARI_SENHA', '')
        self.GRUPO_MAX_NA_CHAMADA = int(g('REDE_GRUPO_MAX_NA_CHAMADA', '4'))

        # E-mail
        self.SMTP_HOST = g('REDE_SMTP_HOST', 'smtp.gmail.com')
        self.SMTP_PORT = int(g('REDE_SMTP_PORT', '587'))
        self.SMTP_USER = g('REDE_SMTP_USER', '')
        self.SMTP_PASSWORD = g('REDE_SMTP_PASSWORD', '')
        self.MAIL_FROM = g('REDE_MAIL_FROM', self.SMTP_USER or 'rede@localhost')
        self.MAIL_BACKEND = g('REDE_MAIL_BACKEND', 'smtp' if self.SMTP_USER else 'console')  # smtp|console|memoria

        # GDMS (caminho 3)
        self.GDMS_MODO = g('REDE_GDMS_MODO', 'simulado')               # desligado | simulado | real
        self.GDMS_BASE_URL = g('REDE_GDMS_BASE_URL', 'https://www.gdms.cloud')
        self.GDMS_CLIENT_ID = g('REDE_GDMS_CLIENT_ID', '')
        self.GDMS_CLIENT_SECRET = g('REDE_GDMS_CLIENT_SECRET', '')
        self.GDMS_USERNAME = g('REDE_GDMS_USERNAME', '')
        self.GDMS_PASSWORD = g('REDE_GDMS_PASSWORD', '')
        self.GDMS_ORG_ID = int(g('REDE_GDMS_ORG_ID', '0') or 0)
        self.GDMS_SITE_ID = int(g('REDE_GDMS_SITE_ID', '0') or 0)
        # E5: como a configuracao inicial chega ao telefone.
        #   api     POST device/config/xml (GDMS entrega quando o aparelho conecta); sem operador
        #   manual  abre tarefa para o operador carregar o XML no painel do GDMS (so se a API falhar na bancada)
        self.GDMS_ENVIO_MODO = g('REDE_GDMS_ENVIO_MODO', 'api')
        # O que vai no XML enviado pelo GDMS:
        #   ponteiro  so P237 (nosso servidor) + travas; a conta SIP vem do nosso servidor (E7). Minimiza dados no GDMS.
        #   completo  conta SIP + P237 + travas (fallback se a bancada mostrar que o aparelho nao rebusca o P237 logo)
        self.GDMS_XML_CONTEUDO = g('REDE_GDMS_XML_CONTEUDO', 'ponteiro')
        # Segredo do caminho do webhook /gdms/eventos/<segredo> (o GDMS nao assina os callbacks)
        self.GDMS_WEBHOOK_SEGREDO = g('REDE_GDMS_WEBHOOK_SEGREDO', '')
        self.GDMS_MAX_TENTATIVAS = int(g('REDE_GDMS_MAX_TENTATIVAS', '6'))

        # Provisionamento
        self.PROV_INTERVALO_MIN = int(g('REDE_PROV_INTERVALO_MIN', '1440'))
        self.MODELO_PADRAO = g('REDE_MODELO_PADRAO', 'grp')

        # Prazos e limites (doc 09)
        self.PRAZO_SEM_BOOT_MIN = int(g('REDE_PRAZO_SEM_BOOT_MIN', '30'))
        self.PRAZO_SEM_REGISTRO_MIN = int(g('REDE_PRAZO_SEM_REGISTRO_MIN', '10'))
        self.VINCULO_EXPIRA_DIAS = int(g('REDE_VINCULO_EXPIRA_DIAS', '30'))
        self.LIMITE_PEDIDOS_PENDENTES = int(g('REDE_LIMITE_PEDIDOS_PENDENTES', '10'))
        self.LIMITE_PEDIDOS_DIA = int(g('REDE_LIMITE_PEDIDOS_DIA', '20'))
        self.LIMITE_MAC_TENTATIVAS_HORA = int(g('REDE_LIMITE_MAC_TENTATIVAS_HORA', '10'))
        self.CODIGO_EMAIL_EXPIRA_MIN = 10
        self.RESET_EXPIRA_MIN = 60

        # Versoes dos textos legais (o hash do texto vai no consentimento)
        self.VERSAO_TERMOS = g('REDE_VERSAO_TERMOS', '2026-10-d')
        self.VERSAO_PRIVACIDADE = g('REDE_VERSAO_PRIVACIDADE', '2026-10-b')
        self.VERSAO_CONSENTIMENTO = g('REDE_VERSAO_CONSENTIMENTO', '2026-10-b')
        # LGPD / ECA Digital (doc 13): quem responde e por onde; retencao dos registros
        self.CONTROLADOR_NOME = g('REDE_CONTROLADOR_NOME', 'Daniel Mariani')
        self.CONTATO_EMAIL = g('REDE_CONTATO_EMAIL', 'contato@telefonefixo.org')          # denuncias e atendimento
        self.PRIVACIDADE_EMAIL = g('REDE_PRIVACIDADE_EMAIL', 'privacidade@telefonefixo.org')  # canal do titular (encarregado)
        self.FAIXA_ETARIA = g('REDE_FAIXA_ETARIA', 'a partir de 6 anos, sempre com um responsável')
        self.RETENCAO_CHAMADAS_DIAS = int(g('REDE_RETENCAO_CHAMADAS_DIAS', '90'))
        # Fase de teste do celular dos pais (doc 08, 6c): o projeto paga, com teto por crianca e por dia.
        self.TETO_CRIANCA_MES = float(g('REDE_TETO_CRIANCA_MES', '5.00'))       # R$ por crianca por mes (0 = sem teto)
        self.TETO_REDE_DIA = float(g('REDE_TETO_REDE_DIA', '20.00'))            # R$ por dia na rede inteira (disjuntor)
        self.TARIFA_SAIDA_MIN = float(g('REDE_TARIFA_SAIDA_MIN', '0.30'))       # estimativa R$/min crianca -> celular
        self.TARIFA_ENTRADA_MIN = float(g('REDE_TARIFA_ENTRADA_MIN', '0.05'))   # estimativa R$/min celular -> crianca
        self.ALERTA_EMAIL = g('REDE_ALERTA_EMAIL', '') or self.CONTATO_EMAIL     # quem recebe os avisos de teto
        self.ALERTA_FRACAO = float(g('REDE_ALERTA_FRACAO', '0.8'))              # avisa ao passar de 80% do teto
