# Deploy — Rede Aberta (resumo)

Automatizado: `deploy/setup-servidor.sh <arquivo.env>` faz tudo abaixo por SSH num Ubuntu 24.04 limpo
(idempotente; usado na bancada em 23/10/2026, ver `bancada/B07-portal-no-ar.md` para as armadilhas:
alembic do Asterisk precisa de SQLAlchemy 1.x; tabelas devem pertencer ao postgres, não ao `portal`;
`sorcery.conf` precisa de `contact=realtime,ps_contacts`).

Servidor Ubuntu 22.04/24.04 (Oracle Ampere A1). Portas: TCP 22, 80, 443, 5060; UDP 10000-20000.

1. **Postgres**: `apt install postgresql`; criar banco `telefone`; rodar `grants.sql` depois das tabelas.
2. **Asterisk** (como no projeto atual, `setup-servidor.sh`) + `asterisk-odbc`, `unixodbc`, `odbc-postgresql`.
   - Tabelas `ps_*` com o alembic do Asterisk: `contrib/ast-db-manage` (`alembic -c config.ini upgrade head`).
   - Copiar `asterisk/extconfig.conf`, `sorcery.conf`, `res_odbc.conf` para `/etc/asterisk/`, `odbc.ini` para `/etc/odbc.ini`.
   - `pjsip.conf` igual ao atual (transport-tcp, external_media_address). `extensions.conf` e `confbridge.conf` desta pasta.
   - Sons: os do projeto atual + gravar `telefone/nao-esta-na-lista`.
3. **Portal**: usuário `rede`; `/opt/rede-aberta/venv` com `pip install -r requirements.txt gunicorn`;
   código em `/opt/rede-aberta/portal`; `/etc/rede-aberta/portal.env` a partir de `portal.env.exemplo`.
   - `flask init-db` (cria o que o alembic não criou), `flask criar-operador email senha`.
   - systemd: `rede-portal.service`, `rede-jobs.timer`, `rede-diario.timer`.
4. **AGIs**: `ln -s /opt/rede-aberta/portal/agi/*.py /usr/share/asterisk/agi-bin/`; usuário `asterisk` precisa ler
   `/etc/rede-aberta/portal.env` (grupo `rede`) e o venv.
5. **nginx + certbot**: `nginx-rede.conf`, `certbot --nginx`.
6. **Backup**: dump diário do Postgres + `/var/backups/rede-aberta/auditoria` para object storage.

Verificação de auditoria pós-deploy: como `portal`, `UPDATE audit_log SET acao='x' WHERE id=1` deve falhar.
