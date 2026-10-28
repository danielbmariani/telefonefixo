# B25 — Chamada em grupo com dois GRP2601 (2026-10-28)

Objetivo: validar ao vivo o que `docs/16` desenha e `deploy/grupos.sh` instala: discar `0` + dígito
toca em todos os membros do grupo, a voz anuncia quem entra e sai, e o histórico registra o tempo
de cada participante. Serviço `rede-grupo` (ARI) em produção desde 28/10, 12h.

## Montagem

- Dois GRP2601 em casa (criança A e criança B, amigas aceitas entre si), portal em telefonefixo.org.
- Grupo criado pela família de A na aba Amigos, com B como membro. Código `01` nos dois telefones.
- Sem terceiro participante: a parte de três pessoas (não atendeu com outros na linha, entrada
  tardia, limite de 4) fica para quando houver um softphone registrado como criança de teste.

## Roteiro executado pelo Daniel (plano de 28/10) e resultado

Relato do Daniel: "Fiz os testes de grupo e todos passaram." O log do serviço e o histórico
confirmam os passos abaixo; os demais (desligar antes de atender, fora do horário de A e de B,
sair do grupo) não deixam linha própria no log e valem pelo relato.

| Passo | Esperado | Log / histórico |
|---|---|---|
| A disca `01#`, B atende, conversam, B desliga | anúncios de chamada em grupo, "B entrou", "B saiu", "você é o único", 30 s depois "a chamada terminou" | 15:24:01 `ALLOW chamar=B`; 15:24:07 `membro B atendeu`; 15:24:11 `2 na chamada`; 15:24:51 `chamada terminou; participantes=[A, B]` |
| Histórico das duas crianças | uma linha por participante, com o tempo em comum | `A GRUPO ALLOWED B:8 47 s` e `B GRUPO ALLOWED A:8 8 s` |
| A disca `02#` | "Esse grupo não existe" | 15:25:21 `codigo 2 -> BLOCK_UNKNOWN GRUPO_NAO_EXISTE`; histórico `02 BLOCKED GRUPO_NAO_EXISTE` |
| A disca `01#` e B não atende | toca 40 s, "ninguém atendeu" | 15:25:28 `ALLOW`; 15:26:05 `chamada terminou; participantes=[A]`; histórico `GRUPO NOANSWER 33 s` |

## O que isso fecha

- Caminho completo em produção: dialplan `_0[1-9]` → Stasis → `rede-grupo` → decisão → ponte →
  anúncios por Piper → registro em `call_logs` com callee `GRUPO` e tempo por par.
- Decisão de 28/10 tomada durante o teste: grupo com no máximo 4 crianças, igual ao limite da
  chamada (antes 8 no grupo e 4 na chamada, com "até 7" e "até 4" em formulários diferentes).

## Pendente

- Três participantes (softphone como terceira criança): anúncio "fulano não atendeu" com outros na
  linha, entrada tardia com "entrando na chamada", tecla `*` com mais de um nome, "chamada cheia".
