# B30 — Segundo tronco: Vono, canais ilimitados (09/11/2026)

Objetivo: tirar a ligação criança → celular do custo por minuto (Nvoip) e passá-la para canais com
ligações ilimitadas (Vono "SIP Trunk Ilimitado"), mantendo a Nvoip como reserva. Pesquisa e decisão
em `docs/17-celular-a-custo-zero.md`. Um canal é uma ligação simultânea da rede inteira, não uma
família. Nenhuma família paga nem configura nada.

## Contratado (Meu Vono, pessoa física)

- SIP Trunk Ilimitado, 4 canais: R$ 200,00/mês, sem fidelidade, ativação grátis. Teto contratual
  de 5.000 min por canal por mês. Domínio SIP `vono2.me`, UDP 5060, registro por usuário e senha.
- Número fixo comum (11) 5444-1774: R$ 32,90/mês, obrigatório ("número à binar"). É o que aparece
  no celular quando a criança liga. A compra do número criou um tronco "Tarifado" (R$ 0/mês) que
  ficou com o número; foi preciso trocar o direcionamento do número para o Ilimitado na aba Números.
- Credenciais só em `~/.config/rede-aberta/bancada.env` (`VONO_HOST`, `VONO_USUARIO`, `VONO_SENHA`,
  `VONO_NUMERO`) e em `/etc/asterisk/pjsip_vono.conf` (640 asterisk). Nunca no repositório.

## Central

- `deploy/asterisk/pjsip_vono.conf.exemplo` + `deploy/tronco-vono.sh`: segundo tronco no molde do da
  Nvoip (registration, auth, aor, endpoint `vono` em `[tronco-entrada]`, identify por `vono2.me`).
  O script só faz `pjsip reload` e `dialplan reload`: os telefones das famílias não caem.
- Dialplan (`[telefones-criancas]`, 9+ID / 8+ID): `[globals] VONO_CANAIS=4`, `VONO_ENDPOINT=vono`.
  Se `GROUP_COUNT(vono) < VONO_CANAIS`, marca o canal com `GROUP()=vono` e disca
  `PJSIP/0<DDD><numero>@vono`; se `DIALSTATUS` for CHANUNAVAIL ou CONGESTION, disca pela Nvoip.
  Sem canal livre, vai direto à Nvoip. Entrada: `GROUP()=${CHANNEL(endpoint)}` para a ligação do
  celular também contar como canal ocupado.
- A Vono exige **0 + DDD + número**: com DDD + número (formato da Nvoip) responde `410 Gone`.
  Com 55 + DDD + número também completa; ficou o 0.

## Execução

| hora (SP) | evento |
|---|---|
| 12:25 | tronco instalado, `vono-reg` Registered em segundos |
| 12:28 | 9+ID do telefone de teste: Vono recusou (410 Gone, 2 s), caiu para a Nvoip, celular tocou pela Nvoip, atendido, **billsec 0** e o telefone seguiu em tom de chamada. Em aberto (ver abaixo) |
| 12:4x | `channel originate` pela Vono: sem prefixo 410; com 0 e com 55, 180/183/200, celular tocou |
| 12:49 | **9+ID pela Vono funcionou**: 22 s, 16 s de conversa, celular mostrou (11) 5444-1774 |
| 12:5x | celular → (11) 5444-1774: "número não existe". Primeira leitura errada ("não chegou à central"): o rastreamento SIP mostrou que o INVITE chegou de 190.89.248.47 e a central respondeu **404**. Duas causas: (a) `identify` só por `vono2.me`, que no reload nem resolveu; (b) a Vono manda no destino o nosso usuário do tronco (`sip:ldem...@central;line=...`), não o número, e `[tronco-entrada]` só tinha `_X.`, `_+X.` e `s` |
| 12:56 | correções: `match=190.89.248.0/24` no identify e `exten => _[a-zA-Z].` em `[tronco-entrada]`. Teste pela própria central (`channel originate` Nvoip → número da Vono): INVITE da Vono aceito, 200 OK, `check_entrada` bloqueou como esperado (chamador era o número da Nvoip) |
| 13:48 | **queda para a Nvoip provada**: com `dialplan set global VONO_ENDPOINT vono-x` a perna Vono falha na hora ("endpoint not found"), a central disca pela Nvoip, celular mostra (11) 5108-3530, 21 s de conversa, áudio normal. O "billsec 0" das 12:28 não se repetiu; fica como ocorrência isolada. `VONO_ENDPOINT` devolvido para `vono` |
| 13:03 | **celular → (11) 5444-1774 funcionou**: 5 s, atendida, chamador identificado (a Vono manda `"55DDDnúmero"`, o 55 já era tratado), áudio nos dois sentidos ("perfeição") |

## Em aberto

1. ~~Entrada pelo número da Vono~~ resolvido às 13:03 (ver tabela).
2. ~~Queda para a Nvoip~~ provada às 13:48. Se o "billsec 0" voltar, rastrear com `pjsip set logger on`.
3. Portal. Feito em 09/11: página Celulares avisa o número que aparece no celular
   (`REDE_TRONCO_NUMERO_SAIDA`); tetos por criança em 300 min de saída e 1.800 de entrada
   (`REDE_TETO_CRIANCA_MES=90.00`, reais-equivalentes a R$ 0,30 e R$ 0,05 por minuto: é um limite de
   minutos, não de dinheiro), rede R$ 1.000 por mês e R$ 100 por dia só no que é pago por minuto.
   Também em 09/11: `call_logs.tronco` ('vono' | 'nvoip', gravado pelo `log_call.py` a partir de
   `CALL_TRONCO`); `custos.gasto_rede_*` ignoram pernas Vono; teto de minutos da Vono
   (`REDE_VONO_CANAIS=4` × 5.000 × 0,8 = 16.000 min/mês): `chamadas.decidir_familia` devolve
   `vono=0` quando encosta e o dialplan vai direto à Nvoip (`FAMILIA_VONO`); aba Uso com minutos
   com celular por tronco; cartão Celulares do painel com "Vono: X de 16.000 min". Com Vono, o
   orçamento da rede deixa de ser dividido por criança no `teto_crianca`. Pendente: confirmar com uma
   ligação real que `tronco` é gravado.
4. Trocar a senha do tronco no Meu Vono (apareceu em capturas de tela durante a contratação) e
   cancelar o tronco Tarifado se não tiver uso.
5. Portabilidade do (11) 5108-3530 da Nvoip para a Vono, para voltar a um número só.
