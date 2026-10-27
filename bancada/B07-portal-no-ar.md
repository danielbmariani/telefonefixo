# B07 — Portal da bancada no ar, com fluxo de ponta a ponta (2026-10-23)

Servidor: Oracle Cloud `VM.Standard.E2.1.Micro`, Ubuntu 24.04, IP 163.176.51.90,
`https://rede-aberta-bancada.duckdns.org` (Let's Encrypt). Instalado por
`portal/deploy/setup-servidor.sh ~/.config/rede-aberta/bancada.env` (idempotente).
Operador da ONG: `ong@rede-aberta-bancada.duckdns.org` (senha em `~/.config/rede-aberta/bancada-operador.txt`).

## O que foi verificado (sem o GRP2601)

| Passo | Como | Resultado |
|---|---|---|
| E1 cadastro + código por e-mail + consentimento | script `e2e.py` via HTTPS (e-mail no journal, `MAIL_BACKEND=console`) | ok |
| E2 criança | `/crianca/nova` | `ps_endpoints/ps_auths/ps_aors` criados no Postgres na mesma transação |
| E3 telefone (MAC + serial) | `/crianca/<id>/telefone` | `dados_informados`; fila GDMS |
| E4/E5 (GDMS simulado) | timer `rede-jobs` (1 min) | `gdms_ok` → `config_enviada` → `aguardando_boot` em menos de 10 s |
| E7 XML | `GET /p/<token>/cfg<mac>.xml` com curl | HTTP 200, 23 P-values (P47, P35, P130=1 TCP, P237, P212=2, P145=0); estado `config_entregue`; `prov_log` com user-agent |
| E8 registro SIP | `sip_register.py`: REGISTER por TCP, digest MD5 com qop=auth, 401 → 200 OK | Asterisk leu o ramal do Postgres (realtime); contato em `ps_contacts`; estado `registrado` no job seguinte |
| Auditoria append-only | `UPDATE audit_log` como `portal` | `permission denied` |
| XML do GDMS (ponteiro) | `flask gdms-xml 2` | só P2, P145, P193, P194, P212, P237, P238, P1414 (sem conta SIP) |

Trilha de auditoria do telefone 2: `crianca_criada ramal_criado telefone_dados_informados
telefone_gdms_ok telefone_config_enviada telefone_config_entregue config_reentregue telefone_sip_registrado`.

## Problemas encontrados e corrigidos no deploy

1. **alembic do Asterisk com SQLAlchemy 2.x roda sem erro e não grava nada** (env.py antigo, sem commit).
   Solução: venv separado `/opt/rede-aberta/venv-alembic` com `sqlalchemy<2`.
2. **Dono das tabelas**: se `portal` é dono e tem UPDATE revogado em `audit_log`, a checagem de FK
   (`SELECT ... FOR KEY SHARE`) falha em todo INSERT de `device_state_history`. Solução:
   `REASSIGN OWNED BY portal TO postgres` antes dos grants (`grants.sql` atualizado).
3. **`sorcery.conf` sem `contact=realtime,ps_contacts`**: o registro ia para o astdb e o portal
   (que lê `ps_contacts`) nunca via o telefone. Corrigido no `deploy/asterisk/sorcery.conf`.
4. `MailerConsole` usava `logging.info`, que o gunicorn não mostra; agora escreve no stderr.
5. `portal.env` com parêntese no `REDE_NOME` quebrava o `source`; valor agora entre aspas.

## Pendente neste servidor

- `GDMS_MODO=real` + `flask gdms-eventos` (B06c) quando o GRP2601 chegar (credenciais já copiadas
  para `/etc/rede-aberta/portal.env` pelo script, se `~/.config/rede-aberta/gdms.env` existir).
- Som `telefone/nao-esta-na-lista` é placeholder (espeak-ng); gravar com a mesma voz dos outros.
- DuckDNS sem cron de atualização (o IP da Oracle é fixo; `DUCKDNS_TOKEN` opcional).
