# Portal do Telefone Fixo

Código do site e da lógica de chamadas do Telefone Fixo (plano original em
`docs/09-plano-caminho-3-zero-touch.md`): cadastro da família, apelido + ID,
MAC + serial, fila de cadastro no GDMS, servidor de provisionamento (`cfgMAC.xml`),
observador de registro SIP, amizades por ID, horários, histórico, painel da ONG e
auditoria append-only em cada etapa.

## Rodar localmente

```bash
cd rede-aberta/portal
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=wsgi:app REDE_DATABASE_URL=sqlite:///rede-dev.db REDE_MAIL_BACKEND=console REDE_GDMS_MODO=simulado
flask init-db
flask criar-operador op@ong.org 'senha-forte' --nome 'Operador'
flask run
```

- `REDE_MAIL_BACKEND=console` imprime os e-mails (código de verificação) no terminal.
- `REDE_GDMS_MODO=simulado` não chama a Grandstream: marca o telefone como cadastrado e
  pronto, para testar o resto do fluxo com um softphone. `real` usa a API (credenciais em
  `deploy/portal.env.exemplo`). `desligado` deixa o telefone parado em `dados_informados`.
- Jobs que em produção rodam por timer: `flask gdms-fila`, `flask jobs-rapidos` (1 min),
  `flask reconciliar`, `flask exportar-auditoria` (diário).

Testes (82, sem rede, SQLite temporário):

```bash
python3 -m pytest -q
```

## Estrutura

```
rede/
  __init__.py        create_app, request_id por request, CSRF, comandos CLI
  config.py          variáveis REDE_* (ver deploy/portal.env.exemplo)
  db.py              esquema SQLAlchemy Core (negócio, auditoria, ps_* do Asterisk)
  auditoria.py       registrar(), consultar() (registra a consulta), linha_do_tempo()
  estados.py         máquina de estados do telefone; única porta para mudar estado
  seguranca.py       PBKDF2, CSRF, rate limit, geração de segredos
  email_envio.py     smtp | console | memoria
  ids.py             ID de 6 dígitos, apelido, classificação do discado
  grandstream_xml.py cfgMAC.xml (P-values do script atual + provisionamento + travas)
  gdms_client.py     API do GDMS (token, assinatura, device/add, log redigido)
  servicos/
    contas.py        E1: cadastro, código por e-mail, consentimento versionado, login, reset, exclusão
    criancas.py      E2: apelido + ID + ramal ps_* na mesma transação
    telefones.py     E3 MAC/serial, token, E7 entrega do XML, reconfigurar, trocar, desativar, reativar, status
    gdms_fila.py     E4/E5: fila com retentativas, interpretação de retCode, tarefa manual de RPS
    amizades.py      pedidos por ID, aceite/recusa/bloqueio silencioso, permitido() para o AGI
    horarios.py, historico.py
    chamadas.py      decidir() — a lógica do AGI check_call, testável
    sip.py           E8: ps_contacts -> registrado/ativo; timeouts; vínculo expirado; alertas
    reconciliacao.py jobs diários + export CSV com SHA-256 + funil
  web/               blueprints: auth, familia, prov (/p/<token>/cfg<mac>.xml), admin (/ong)
  templates/, static/, textos/ (termos, privacidade, consentimento: RASCUNHOS para o jurídico)
agi/                 check_call.py, check_group.py, log_call.py (usam rede.servicos), conf_leave.py, hora_certa.py
deploy/              extensions.conf (6 dígitos), realtime (extconfig/sorcery/odbc), systemd, nginx, grants.sql
tests/               82 testes: fluxo HTTP, provisionamento, estados/jobs, amizades/chamadas, celulares, custos, LGPD, segurança
```

## Estados do telefone

`dados_informados → gdms_cadastrado → aguardando_boot → config_entregue → registrado → ativo`,
com `erro_gdms_conflito`, `erro_dados`, `sem_boot`, `sem_registro`, `desativado`. Toda transição
grava `device_state_history` + `audit_log` (ver `rede/estados.py`).

## Bancada

Zero-touch pelo GDMS, boot, XML, webhook, reset e conflito foram confirmados com aparelhos reais;
o registro de cada teste está em `bancada/README.md` (B01 a B23). O que ainda falta está marcado
lá como pendente.

## Decisões de implementação

- **Postgres em produção, SQLite nos testes.** SQLAlchemy Core sem ORM. Auditoria append-only é
  garantida por grants do Postgres (`deploy/grants.sql`), não pelo código.
- **Segredos no banco**: `senha_sip` (o Asterisk exige em claro em `ps_auths`), `prov_tokens.token`
  (vai na URL do P237) e `telefones.admin_senha` ficam em claro, mesma classe de exposição; nunca
  aparecem em `audit_log` (`auditoria.redigir`). Rotação pelo portal ("Reconfigurar").
- **Celular da família** sai por um tronco SIP (Nvoip) para até dois números por família: a criança
  disca 9 + ID para o primeiro e 8 + ID para o segundo; o número recebe de volta pelo mesmo tronco.
  Minutos limitados por criança e por dia (`servicos/custos.py`); ver `bancada/B23-tronco-celular-dos-pais.md`.
- **Rate limits** em memória (um processo). Com mais workers do gunicorn, mover para o banco.
