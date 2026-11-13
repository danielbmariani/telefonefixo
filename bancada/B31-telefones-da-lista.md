# B31 — Telefones da lista da família: saída pela central (13/11/2026)

Objetivo: provar que a criança liga, pelo telefone, para um número cadastrado na lista da família
discando o número (do DDD da casa) ou DDD + número, e que número fora da lista ouve a frase nova.
Plano e decisões em `docs/20-plano-telefones-da-familia.md`; proposta em `docs/19`.

## O que foi publicado (13/11, manhã)

- `deploy/codigo.sh`: colunas `familias.ddd`, `familias.ddd_origem` e `familia_telefones.recebe`
  (`BOOLEAN DEFAULT true NOT NULL`, linhas antigas ganharam `true`); `rede/ddd.py` com a base de
  municípios (5.571, MIT); `ids.classificar_discado` com `externo_local` (8 e 9 dígitos) e `externo`
  (10 e 11, com 0 ou 55 na frente); `familia_telefones.casar_discado` (pelo fim do número, DDD da casa
  desempata); `chamadas.decidir_externo`; `custos._saida` conta destino de 10/11 dígitos; histórico com
  o nome da lista. 163 testes.
- `deploy/tronco-vono.sh`: `extensions.conf` com os padrões novos e a sub-rotina `[saida-tronco]`
  (Vono com queda para Nvoip, `h` próprio), `dialplan reload` sem reiniciar. Conferido no servidor:
  `34567890` → `_[2-5]XXXXXXX`, `987654321` → `_9XXXXXXXX`, `1134567890` → `_[1-9][1-9][2-5]XXXXXXX`,
  `11987654321` → `_[1-9][1-9]9XXXXXXXX`, `01134567890` e `5511987654321` nos padrões com prefixo;
  `9736534`, `345678`, `100` e `01` continuam nos padrões de antes. Nenhum erro no reload.
- Frases Piper geradas em `/var/lib/rede-aberta/sons/frases/`: `nao-esta-na-lista-de-casa` e
  `disque-com-ddd`.
- Sem mudança no aparelho (dial plan `x+`, 4 s, `#`).

## Roteiro (telefone do jose, família do Daniel: um celular cadastrado, "Pai", DDD 11; DDD da casa
ainda não definido, de propósito: o casamento é só pelo fim do número)

| # | Discar no GRP | Esperado | Resultado |
|---|---|---|---|
| 1 | `11` + número do celular + `#` (11 dígitos) | celular toca com (11) 5444-1774; áudio nos dois lados; `call_logs`: `callee_ext` = número completo, `tronco = vono` | |
| 2 | só o número do celular + `#` (9 dígitos) | igual ao 1 (casou pelo fim do número) | |
| 3 | `0` + `11` + número + `#` (12 dígitos) | igual ao 1 | |
| 4 | `11 3456 7890 #` (não está na lista) | "Esse telefone não está na lista de casa. Peça para cadastrar no site."; `call_logs` BLOCKED `EXTERNO_FORA_DA_LISTA` | |
| 5 | pausa de 5 s no meio dos dígitos | o aparelho envia o que tinha; conferir o que a central fez | |
| 6 | `9` + ID + `#` (atalho de sempre) | continua funcionando pela sub-rotina nova | |

## Execução (13/11/2026, 11:24 a 11:27, telefone do jose)

Relato do Daniel: 1 funcionou, 2 funcionou, 3 funcionou, 4 ouviu a frase nova, 5 funcionou, 6 ouviu
"esse número não existe". Conferência em `call_logs` (horário de SP) e no CDR do Asterisk (UTC):

| hora | discado | central | `call_logs` | CDR |
|---|---|---|---|---|
| 11:24:29 | 11 + celular (11 dígitos) | `_[1-9][1-9]9XXXXXXXX` → Vono | ALLOWED, 5 s, `callee_ext` = número completo, `tronco = vono` | Dial `PJSIP/0<num>@vono`, ANSWERED, 11 s |
| 11:24:43 | número fora da lista (10 dígitos) | `BLOCK_EXTERNO` | BLOCKED `EXTERNO_FORA_DA_LISTA` | Answer + frase, 1 s |
| 11:25:28 | só o celular (9 dígitos) | `_9XXXXXXXX` → casou pelo fim → Vono | ALLOWED, 7 s, número completo, vono | ANSWERED, 15 s |
| 11:25:51 | 0 + 11 + celular (12 dígitos) | `_0[1-9][1-9]9XXXXXXXX` → Vono | CANCEL (desligou tocando) | Dial pela Vono, sem atender, 6 s |
| 11:26:37 | 9 + ID | `_[89][2-7]XXXXX` → sub-rotina nova → Vono | CANCEL (desligou tocando) | Dial pela Vono, 5 s |
| 11:27:00 | 5 dígitos (pausa no meio) | `_X.` "número bloqueado" | nada (como antes) | Answer + "número inválido" |

Observações:
- O `L()` do Dial trouxe o teto certo: 16.920.000 ms = 282 min restantes dos 300 do mês (as ligações
  anteriores já tinham consumido 18 min-equivalentes).
- Uma linha por ligação em `call_logs`: o `h` da sub-rotina e o caminho normal não duplicaram.
- Fixo pela Vono continua sem prova (o Daniel escolheu testar com o próprio celular). Fica para a
  primeira família que cadastrar um fixo, ou para um teste com um fixo conhecido.
- Pausa de 5 s no meio: o aparelho enviou os 5 dígitos que tinha; a central respondeu "número inválido",
  sem tocar em ninguém. Comportamento igual ao de antes.

**Resultado: provado.** Etapas A (base e DDD) e B (saída) do doc 20 estão no ar. Faltam C (telas) e
D (entrada com `recebe` e menu pelos nomes).

## Parte 2: entrada com menu pelos nomes (13/11/2026, tarde)

Publicado: `familias_por_numero` (todas as famílias com o número e `recebe`), `decidir_entrada` devolvendo
`MENU` quando mais de uma família tem criança que pode tocar, `check_entrada.py` com `ENTRADA_OPCOES`,
`ENTRADA_NOMES` e `ENTRADA_LIMITES`, ramo `menu` em `[tronco-entrada]` (`Read()` com as frases "Para falar
com" + apelido + "tecle N", duas tentativas, "não deu certo" no fim) e dez frases Piper novas. 168 testes.

Montagem: família de teste "Bancada B31" (criança `testemenu`, aparelho fictício em estado ativo) com o
celular 1 do Daniel cadastrado como "Vô (teste)". Do celular, o número da rede passou a oferecer três
opções: jose (1) e teste3 (2), da família do Daniel, e testemenu (3).

| hora (SP) | o que fez | ouviu / aconteceu | registro |
|---|---|---|---|
| 13:04 | ligou e teclou 2 | tocou no telefone do teste3; desligou tocando | `call_logs` CANCEL para 71****; CDR Dial `PJSIP/71...` 41 s |
| 13:05 | ligou e teclou 1 | tocou no jose, atendido, 12 s | `call_logs` ALLOWED 12 s para 73****, tronco nvoip; CDR Dial `PJSIP/73...` |
| 13:0x | não teclou nada | menu repetido, "não deu certo", desligou | sem Dial (como desenhado) |
| 13:0x | teclou 3 (testemenu, sem aparelho real) | não atendeu | sem linha em `call_logs` (Dial para endpoint sem contato) |

Relato do Daniel: "todos os testes passaram". Observação dele: o apelido `testemenu` saiu rápido demais
na voz, difícil de entender. Causa: apelido sem separador vira uma palavra só para o Piper. Com `_` o
`voz.texto_do_apelido` já separa ("maria_clara" → "maria clara") e lê dígitos um a um ("jose07" → "jose
0 7"); `-` não existe em apelido (só letras, dígitos e `_`). Melhoria possível, não feita: gerar os
apelidos com `length_scale` maior (1,25 em vez de 1,1) só para o menu.

Família de teste excluída pelo caminho oficial (`contas.excluir_conta`) e o aparelho fictício apagado.

**Resultado: provado.** Etapa D fechada. O doc 20 está inteiro no ar; fica pendente só o fixo pela Vono.

