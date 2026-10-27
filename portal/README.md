# Portal — Rede Aberta (caminho 3, zero-touch)

Código do portal da rede aberta, partindo do `telefone_fixo/web/` e implementando o
plano do `docs/09-plano-caminho-3-zero-touch.md`: cadastro da família, apelido + ID,
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

Testes (42, sem rede, SQLite temporário):

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
tests/               42 testes: fluxo HTTP E1-E3, provisionamento, estados/jobs, amizades/chamadas, ONG, unitários
```

## Estados do telefone

`dados_informados → gdms_cadastrado → aguardando_boot → config_entregue → registrado → ativo`,
com `erro_gdms_conflito`, `erro_dados`, `sem_boot`, `sem_registro`, `desativado`. Toda transição
grava `device_state_history` + `audit_log` (ver `rede/estados.py`).

## O que a bancada ainda precisa confirmar (doc 09, seção 7)

- Códigos de erro do `device/add` já vêm da tabela oficial (`gdms_client.ERROS_DEVICE_ADD`);
  confirmar 30011 entre contas diferentes (B13) e 30010 com serial real (B14).
- E5 por API (`GDMS_ENVIO_MODO=api`, `device/config/xml`): o GDMS aceita e entrega a aparelho
  offline? (B06b). Se não, `manual` abre tarefa no painel e `flask gdms-xml <id>` imprime o XML.
- `GDMS_XML_CONTEUDO=ponteiro` (só P237 + travas) basta? Senão `completo` (B09).
- Webhook: `flask gdms-eventos` depois que o site estiver em HTTPS; conferir que o evento chega (B06c).
- P-values do GRP2601 para provisionamento (P237/P6767/P194/P193) e travas de menu:
  `grandstream_xml.py` marca o que é "A CONFIRMAR".
- O GRP usa os P-values base do GXP (P72 = # envia). Confirmar.

## Decisões de implementação

- **Postgres em produção, SQLite nos testes.** SQLAlchemy Core sem ORM. Auditoria append-only é
  garantida por grants do Postgres (`deploy/grants.sql`), não pelo código.
- **Segredos no banco**: `senha_sip` (o Asterisk exige em claro em `ps_auths`), `prov_tokens.token`
  (vai na URL do P237) e `telefones.admin_senha` ficam em claro, mesma classe de exposição; nunca
  aparecem em `audit_log` (`auditoria.redigir`). Rotação pelo portal ("Reconfigurar").
- **Celular da família (Groundwire)** ainda não foi portado: o dialplan devolve "número inválido"
  para 8/9 + ID e o AGI registra `FAMILIA_NAO_CONFIGURADA`.
- **Rate limits** em memória (um processo). Com mais workers do gunicorn, mover para o banco.
