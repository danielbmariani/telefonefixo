# B12 — "Remover telefone" zera o aparelho e tira do GDMS (2026-10-28)

Objetivo: a família aperta um botão e o aparelho fica como novo, fora da rede, sem operador.
Motivo: o Daniel vai emprestar um dos dois GRP2601 à Rita (Desconecta) para ela cadastrar como
telefone novo e sentir o site. Implementado nesta data (`gdms_fila` etapas `zerar` e `remover_gdms`).

## O que aconteceu (aparelho da criança A, `ativo` desde 26/10)

| hora | evento | fonte |
|---|---|---|
| 16:06:40 | família apertou "Remover telefone" → `desativado`, item na fila `zerar` | audit `telefone_desativar` |
| 16:06:55 | `device/config/xml` com a configuração de fábrica (`pvalues_fabrica`), aplicar=sim → retCode 0 | gdms_log |
| 16:06:56 | `task/add` tipo 2 (reset de fábrica) → retCode 0 | gdms_log |
| ~16:07 | relato do Daniel: aparelho piscou, mostrou "sem rede", voltou ligado **sem o ID** | visor |
| 16:09:00 | callback do GDMS alertType 5 (reboot) para o MAC; o portal registra `mac_desconhecido` porque o telefone já está desativado (esperado) | gdms_eventos |
| 16:09 | Asterisk: só o outro aparelho e o tronco registrados; o removido sumiu dos contatos | `pjsip show contacts` |
| 16:10:25 | `device/delete` → retCode 0; fila `ok`; audit `gdms_removido` | gdms_log |

Nenhuma tarefa de operador foi aberta. Nenhum callback alertType 2 (factory reset) chegou antes de o
MAC sair da org, só o de reboot. Na B11 o reset pela web gerou alerta 2 e depois 5. Então o mais
provável é que a **configuração de fábrica aplicou e reiniciou o aparelho**, e o reset pela API
(já suspeito na B11) não executou ou executou depois da remoção, sem callback. Na prática não faz
diferença: conta apagada, senha admin padrão, travas abertas, servidor de configuração de volta ao
da Grandstream.

## O que fecha

- Fluxo "telefone de segunda mão" sem operador: botão → aparelho zerado em ~2 min → MAC fora da
  org em ~4 min. A tarefa `remover_gdms` só nasce se o `device/delete` falhar.
- Texto do botão e da mensagem sem "outra família pode cadastrá-lo" (pedido do Daniel: soava como
  se alguém pudesse cadastrar o aparelho como filho dele).

## Pendente

- Segunda metade: a Rita cadastra o mesmo MAC numa conta nova. Esperado: `device/add` retCode 0
  (MAC livre), configuração entregue, registro. Isso cobre também a B13 na variante "mesma org,
  outra conta do site".
- Confirmar num reset pela web (B11) se o reset pela API funcionaria com P22373=0 já aplicado.
  Baixa prioridade: a configuração de fábrica resolve o caso de uso.
