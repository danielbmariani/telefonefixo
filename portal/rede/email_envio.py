"""email_envio.py — Envio de e-mail com tres backends: smtp, console (dev) e memoria (testes)."""

import logging
import sys
import smtplib
from email.message import EmailMessage


class MailerSMTP:
    def __init__(self, cfg):
        self.cfg = cfg

    def enviar(self, para, assunto, corpo):
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = self.cfg.MAIL_FROM
        msg['To'] = para
        msg.set_content(corpo)
        with smtplib.SMTP(self.cfg.SMTP_HOST, self.cfg.SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(self.cfg.SMTP_USER, self.cfg.SMTP_PASSWORD)
            recusados = s.send_message(msg)
            # smtplib descarta a resposta final do servidor; guardamos o que ele devolve no QUIT
            # e os destinatarios recusados, para rastrear um envio "aceito mas nao entregue".
            codigo, resposta = s.noop()
        # stderr -> journal do gunicorn (logging.info some no gunicorn padrao).
        print(f'EMAIL-SMTP para={para} assunto={assunto!r} host={self.cfg.SMTP_HOST} '
              f'recusados={recusados or "nenhum"} noop={codigo}', file=sys.stderr, flush=True)


class MailerConsole:
    """Escreve o e-mail no stderr (vai para o journal do gunicorn). Para bancada/dev."""
    def enviar(self, para, assunto, corpo):
        print(f'EMAIL para={para} assunto={assunto}\n{corpo}\nFIM-EMAIL', file=sys.stderr, flush=True)


class MailerMemoria:
    def __init__(self):
        self.enviados = []

    def enviar(self, para, assunto, corpo):
        self.enviados.append({'para': para, 'assunto': assunto, 'corpo': corpo})

    def ultimo_para(self, email):
        for m in reversed(self.enviados):
            if m['para'] == email:
                return m
        return None


def criar_mailer(cfg):
    if cfg.MAIL_BACKEND == 'smtp':
        return MailerSMTP(cfg)
    if cfg.MAIL_BACKEND == 'memoria':
        return MailerMemoria()
    return MailerConsole()
