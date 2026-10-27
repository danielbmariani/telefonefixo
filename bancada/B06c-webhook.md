# B06c — Webhook do GDMS (2026-10-26)

`flask gdms-eventos` (como usuário `rede`, via `systemd-run` com o `EnvironmentFile` do portal):
`callback/set_url` retCode 0, `subscribe/save` retCode 0. `subscribe/info` confirma a assinatura da
org <org_id>: deviceStatus, accountStatus e alertas 0, 2, 5, 7, 9.

Eventos recebidos em `POST /gdms/eventos/<segredo>` (IPs de origem 52.40.91.108 e 44.234.70.128,
user-agent `Apache-HttpClient/4.5.13 (Java/17.0.11)`), tudo gravado em `gdms_log` e no audit:

| hora | mensagem | o que o portal fez |
|---|---|---|
| 12:23:00 | alerta 2 (factory reset), estado `aguardando_boot` | audit `gdms_alerta_reset_de_fabrica` (abriu caso: falso positivo, ver abaixo) |
| 12:24:00 | deviceStatus online | `gdms_online_em`, audit `gdms_aparelho_online` |
| 12:24:00 | alerta 5 (reboot, `rebootMode 1`) | audit `gdms_alerta_reboot` |

Segredo errado na URL: 404 (testado com curl). Nenhum evento `accountStatus` (conta SIP não passa pelo
GDMS no modo ponteiro).

Correções que saíram daqui (código + testes):
- O GRP2601 manda o alerta "factory reset" no **primeiro boot de fábrica**. O caso `reset_de_fabrica`
  agora só abre se o telefone já tinha buscado configuração antes (`config_entregue_em`).
- Caso `ip_divergente_sip` falso: `ps_contacts.via_addr` traz o IP privado da casa (192.168.1.32); o
  observador passou a usar o host da URI do contato reescrita pelo Asterisk (`rewrite_contact`), que é
  o IP público, igual ao do provisionamento.
