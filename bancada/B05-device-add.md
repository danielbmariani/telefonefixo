# B05 — device/add via API (2026-10-23)

Aparelho informado pelo Daniel: MAC EC74D7XXXXXC, S/N 35304JXXXX.

**Atenção: o GDMS identificou o aparelho como `deviceType: "HT802V2"`, firmware 1.0.5.4,
IP privado 192.168.1.51, IP público 191.32.207.123.** Ou seja, não é um GRP2601: é o adaptador
HT802V2 da rede atual (telefone_fixo). A confirmar com o Daniel. O aparelho foi adicionado à
organização "Rede Aberta - bancada" (<org_id>) e deve ser REMOVIDO do GDMS antes de qualquer
RPS/template, para não interferir na rede atual.

Resultados:
- 2FA por e-mail ativado na conta: o token da API continua funcionando (B02b).
- `device/add` com `siteId` <site_id> (site da org Default): `retCode 0`, mas
  `data.failure 1`, `errorDeviceList[0].errorMsg = "50025"`. **retCode 0 não significa sucesso**;
  o detalhe por aparelho está em `data.success/failure/errorDeviceList`.
- `device/add` sem `siteId`: `success 1`. O aparelho foi para o site padrão da org (<site_id>).
  Cada organização tem o próprio site "Default"; `site/list` só devolveu o da org Default.
- Repetir o mesmo `device/add`: errorMsg **30007** (já está na organização).
- Mesmo MAC na org Default (mesma conta): errorMsg **30011** (está em outra organização).
- Serial errado: deu 50025 por causa do siteId, antes de chegar a validar o serial. **B14 refazer**
  sem siteId, com o GRP2601 real.
- `device/list` devolve: deviceType, mac (com dois-pontos), sn, publicIp, privateip,
  firmwareVersion, lastTime, status, siteId/siteName, isSynchronized.

Implementado no portal: `gdms_client.resultado_device_add()` (lê errorDeviceList),
`ERROS_DEVICE_ADD` {30007, 30011, 50025}, siteId omitido quando 0; `gdms_fila` usa isso.

Referência da API (captura do Daniel, doc.grandstream.dev): o menu tem Overview (API Instructions,
Get Start, Signature Method, Interfaces Overview, Common Parameters, **The format of the xml
configuration**), OAuth2.0, API Reference (Obtain/Refresh Token, Organization, Site, **Device
Interfaces**, SIP Server, SIP Account, **Task Interfaces**). **Não há seção de RPS.** A introdução
cita "configure parameters" para aparelhos e uma "WebHook Listener-based API" (eventos do aparelho
empurrados para terceiros). Hipótese para o E5 sem operador: em vez de RPS, empurrar P237 (Config
Server Path) por API via Device Interfaces/Task. Depende das páginas "Device Interfaces" e
"The format of the xml configuration", ainda não capturadas.

## Refeito com o GRP2601 real (2026-10-26)

Aparelho: GRP2601, MAC EC74D7XXXXXA, S/N 35103ZXXXXA, firmware de fábrica 1.0.7.11.
Fluxo normal do portal (família cadastrou S/N e MAC às 11:58:46; fila `gdms-fila` do minuto seguinte):

- `oauth/token` ok; `device/list` da org <org_id>: vazia (HT802V2 já removido).
- `device/add` sem siteId: `retCode 0`, `data.success 1, failure 0` (11:58:48).
- `device/config/xml` com o aparelho **desligado**: `retCode 0` (11:58:49). Ver B06b.
- `device/list` depois do boot: `deviceType GRP2601`, `isSynchronized 1`, `status 1`, publicIp/privateip da casa.

Observação: a senha do GDMS tem aspas duplas dentro; sem aspas simples no `.env` o shell e o
`EnvironmentFile` do systemd engolem as aspas e o token falha com `invalid_grant / Bad credentials`.
Corrigido com `REDE_GDMS_PASSWORD='...'` (aspas simples) nos dois lugares.
