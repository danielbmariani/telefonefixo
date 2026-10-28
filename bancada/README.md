# Bancada — evidências da validação (doc 09, seção 7)

Um arquivo por teste, nomeado `Bnn-descricao.{md,txt,log}`. Capturas e vídeos ficam fora do git
(ver `.gitignore`); referencie o nome do arquivo no `.md`.

Cada `Bnn-*.md` tem: data, aparelho (modelo, MAC, serial, firmware), o que foi feito, resultado,
evidência (trecho de log colado), decisão que isso fecha.

| # | Teste | Status | Arquivo |
|---|---|---|---|
| B01 | Conta GDMS da ONG, 2FA, organização dedicada | feito (2FA pendente) | B01-conta-gdms.md |
| B02 | API Developer: client_id/secret; token via `gdms_client.py` | feito | B02-B03-api-token-org-site.md |
| B03 | `org/list`, `site/list` → IDs para `portal.env` | feito: org <org_id>, site <site_id> | B02-B03-api-token-org-site.md |
| B04 | P-values do GRP2601 | feito: template oficial em `referencia-pvalues/`; P9996 = User Protection, P22030 = Validate Hostname; travas em B04 | B04-pvalues-grp2601.md |
| B05 | `device/add` via API | feito com o GRP2601 (26/10): success 1 | B05-device-add.md |
| B06 | E5 por API: existe? | **sim**: `device/config/xml` entrega XML ao aparelho; webhook (`subscribe/save`) avisa online/registro/reset. Implementado no portal | B06-api-referencia.md |
| B06b | `device/config/xml` com aparelho **offline**: aceito? entregue no primeiro boot? multipart ok? | **sim, sim, sim** (26/10): aplicado no primeiro boot, sem toque | B06b-config-xml-offline.md |
| B06c | Webhook: `flask gdms-eventos` registra a URL; evento chega ao portal no boot | feito: factory reset, online, reboot recebidos; 2 falsos positivos corrigidos | B06c-webhook.md |
| B07 | Servir `cfg<mac>.xml` pelo portal em HTTPS | feito: portal no ar em `rede-aberta-bancada.duckdns.org`; fluxo E1–E8 testado com curl + REGISTER | B07-portal-no-ar.md |
| B08 | Boot de fábrica → requisição chega? tempo? user-agent? | feito: ~1,5 min; UA `Grandstream Model HW GRP2601 SW 1.0.7.11 DevId <mac>` | B08-B09-B18-primeiro-boot.md |
| B09 | Aparelho aplicou: registrou no Asterisk; P237 gravado; menu travado | registrou; P237 provado (buscou no nosso servidor); travas P1357/P22373/P1650/P276/P8469 enviadas, menu a confirmar | B08-B09-B18-primeiro-boot.md |
| B10 | Religar: rebusca? intervalo de recheck (P193) | feito (26/10): volta e registra sozinho | B10-B11-religar-e-reset.md |
| B11 | Reset de fábrica mantendo no GDMS → volta sozinho? | **sim** (26/10): ~2 min, caso aberto para a ONG; reset por API (`task/add`) não funcionou | B10-B11-religar-e-reset.md |
| B12 | Remover do GDMS + reset → nada chega (fluxo "reativar") | pendente | |
| B13 | `device/add` do mesmo MAC em outra conta → retCode do conflito | pendente | |
| B14 | `device/add` com serial errado → retCode | código oficial 30010 (tabela da referência); confirmar com GRP2601 | B06-api-referencia.md |
| B15 | GRP2601 nº 2: repetir B05/B08; ligação entre os dois | feito (26/10): 2 min até conectar; ligação de 15 s ok | B15-segundo-aparelho-e-primeira-ligacao.md |
| B16 | GRP2602W: Wi-Fi pelo teclado, cronometrar | pendente | |
| B17 | GXP1610: confirmar que não serve ao zero-touch | pendente | |
| B18 | HTTPS Let's Encrypt aceito pelo GRP? certificado inválido recusado? | Let's Encrypt aceito de fábrica (fw 1.0.7.11); certificado inválido a testar | B08-B09-B18-primeiro-boot.md |
| B19 | Remover do GDMS após provisionado: continua funcionando? | pendente | |
| B20 | Termos do GDMS: dados e localização | pendente | |
| B21 | Teclas rápidas (VPK 2, 7, 8) aparecem no GRP2601? Enviadas pelo GDMS em 26/10 14:33 | pendente: conferir no aparelho | |
| B22 | Resync por SIP NOTIFY check-sync (P4428) para rebuscar o cfg sem esperar o dia | pendente | |
| B23 | Tronco de operadora: 9+ID toca no celular do responsável; celular cadastrado toca no telefone da criança | **feito** 27/10: Nvoip, nos dois sentidos, com áudio; R$ 39/mês o número | B23-tronco-celular-dos-pais.md |
| B24 | GRP2602W (Wi-Fi): conferir no aparelho o caminho do menu (Menu > System > Wi-Fi Settings > Enabled > Scan > senha), o número de teclas ao lado do visor (desenho do site), o nome do modelo na etiqueta de baixo e se a senha do Wi-Fi pode ir na configuração (primeira ligação por cabo) | pendente: precisa de um GRP2602W | |
| B25 | Chamada em grupo (doc 16): dois GRP2601; visor "Grupo: <nome> (<apelido>)", anúncios (chamando, entrou, saiu, ninguém atendeu, único, terminou), grupo inexistente, histórico com tempo por participante | feito com dois aparelhos (28/10); três participantes pendente (precisa de softphone) | B25-chamada-em-grupo.md |

Saídas que entram no código: `ERROS_DEVICE_ADD` em `portal/rede/gdms_client.py` (B13, B14),
P-values em `portal/rede/grandstream_xml.py` (B09, B10), `GDMS_XML_CONTEUDO` ponteiro/completo (B09),
tempos dos cronômetros em `portal/rede/servicos/telefones.py::status` (B08).

Comando útil para a bancada (dry-run monta a requisição sem enviar):

```bash
cd ../portal && set -a && . ~/.config/rede-aberta/gdms.env && set +a
python3 -m rede.gdms_client --client-id "$REDE_GDMS_CLIENT_ID" --client-secret "$REDE_GDMS_CLIENT_SECRET" \
  --username "$REDE_GDMS_USERNAME" --password "$REDE_GDMS_PASSWORD" devices --org-id <org_id>
# subcomandos: orgs | sites | devices | add | config-xml --mac --org-id --xml arq | status --mac |
#              detail --mac | delete --mac --org-id | callback --url | assinar-eventos --org-id |
#              assinatura | eventos-disponiveis | templates --org-id      (--dry-run monta sem enviar)
```
