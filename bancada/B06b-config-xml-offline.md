# B06b — `device/config/xml` com o aparelho desligado (2026-10-26)

Aparelho: GRP2601, MAC EC74D7XXXXXA, S/N 35103ZXXXXA, firmware 1.0.7.11, de fábrica, nunca ligado.

O que foi feito: fluxo normal do portal (modo `real`, `GDMS_XML_CONTEUDO=ponteiro`). A fila fez
`device/add` e em seguida `device/config/xml` (multipart: `file` com o XML ponteiro, `mac`, `orgId`,
`applyConfig=true`) às 11:58:49, com o telefone ainda na caixa.

Resultado:
- Multipart e assinatura do formulário aceitos: `retCode 0` na hora.
- Telefone ligado pela família por volta de 12:22. Às 12:23:00 o GDMS mandou o alerta `factory reset`
  (primeiro contato), e às **12:23:43** o telefone pediu `cfgec74d7xxxxxa.xml` no nosso servidor
  (user-agent `Grandstream Model HW GRP2601 SW 1.0.7.11 DevId ec74d7xxxxxa`) e recebeu `entregue`.
  Ou seja: a configuração enviada pela API com o aparelho offline foi aplicada no primeiro boot, sem
  reset, sem ninguém tocar no menu.
- Tempo entre ligar e buscar a nossa configuração: cerca de 1 a 2 minutos (inclui obter IP, falar com
  o GDMS, aplicar o ponteiro e rebootar: alerta `reboot` às 12:24:00).

Decisão que isso fecha: E5 por API funciona (ponteiro P237 + locks via `device/config/xml`); não
precisa de RPS, template nem operador. Mantém-se o modo `ponteiro` (segredos SIP só no nosso servidor).

Observação: `device/account/status` devolve `sipAccountInfoList: []` porque a conta SIP não passa pelo
GDMS (vem do nosso cfg). O evento `accountStatus` do webhook portanto não vem nesse modo; o registro
é comprovado pelo Asterisk (B09).
