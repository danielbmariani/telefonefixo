# B02/B03 — Token da API, org/list, site/list

Data: 2026-10-23. Ferramenta: `portal/rede/gdms_client.py` (GdmsClient real, sem dry-run).

Resultado: **funciona exatamente como documentado no GDMS API Guide.**

- `POST /oapi/oauth/token` com password = SHA256(MD5(senha)) → HTTP 200, `token_type: bearer`,
  `scope: read write`, **`expires_in: 86399` (24 h, e não 1 h como o guia sugere)**. Refresh token presente.
- `GET /oapi/v1.0.0/org/list` (assinatura SHA256 da base `&access_token=..&client_id=..&client_secret=..&timestamp=..&`)
  → `retCode 0`. Organizações: Default (<org_default_id>, isDefault 1) e "Rede Aberta - bancada" (<org_id>).
- `GET /oapi/v1.0.0/site/list` → `retCode 0`. Um site: "Default" (<site_id>, isDefault 1). Não ficou claro
  a qual organização pertence (sem parâmetro de org na chamada); ver B03b abaixo.
- Latência: ~900 ms por chamada.

Valores para o `portal.env` (a confirmar o site da org <org_id>):

```
REDE_GDMS_ORG_ID=<org_id>
REDE_GDMS_SITE_ID=<site_id>   # a confirmar
```

Decisões fechadas: assinatura e hash de senha do `gdms_client.py` estão corretos; o refresh pode ser
a cada 12 h em vez de 1 h (manter 55 min por segurança não custa nada).

## B03b — Descobertas além do guia (2026-10-23)

- **Parâmetros extras na query exigem entrar na assinatura**, em ordem alfabética de nome
  (`&access_token=..&client_id=..&client_secret=..&orgId=..&timestamp=..&`). Sem isso: HTTP 200 com
  `retCode 40003 "bad signature"`. Implementado em `gdms_client.assinar(params=)`.
- **`POST /oapi/v1.0.0/device/list`** existe (GET devolve 405). Corpo `{"orgId", "pageNum", "pageSize"}`
  → `{"data": {"result": [], "total": 0}, "retCode": 0}`. Serve para idempotência do `device/add` e
  para a reconciliação GDMS × banco (já ligados no portal).
- `site/list` devolve o mesmo site <site_id> com ou sem `orgId` (<org_default_id> ou <org_id>): o site parece ser da
  conta, não da organização. `REDE_GDMS_SITE_ID=<site_id>` confirmado.
- Não existem (404): `rps/list`, `rpsServer/list`, `rps/server/list`, `device/rps/list`. O caminho real do
  gateway aparece nos 404 como `/gateway/v1.0.0/...`. A associação ao RPS continua sem endpoint
  conhecido → B06 depende da referência completa em doc.grandstream.dev (só abre no navegador).
