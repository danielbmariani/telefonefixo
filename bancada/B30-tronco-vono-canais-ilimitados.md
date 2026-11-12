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
   orçamento da rede deixa de ser dividido por criança no `teto_crianca`. Confirmado às 14:33 com ligação real: 9 s,
   `tronco = 'vono'` em `call_logs`.
4. Trocar a senha do tronco no Meu Vono (apareceu em capturas de tela durante a contratação) e
   cancelar o tronco Tarifado se não tiver uso (a Vono confirmou em 09/11 que não afeta o Ilimitado;
   cuidado para excluir o Tarifado e não o Ilimitado).
5. Portabilidade do (11) 5108-3530 da Nvoip para a Vono, para voltar a um número só. Passo a passo
   da Vono (09/11): pôr R$ 32,90 de saldo no painel, pedir a portabilidade e avisar o Alan, que
   acompanha e manda a documentação necessária. Decisão só em 23/11, depois de duas semanas de
   Vono em uso: cron no servidor manda e-mail "Lembrete: portabilidade do (11) 5108-3530 para a
   Vono" às 9h desse dia, com o passo a passo e os itens 4 e 5; apaga-se sozinho depois de rodar.
6. ~~E-mail no cadastro~~: a proposta nº 01234 saiu com `gmail.om`; o cadastro estava errado mesmo e
   a Vono corrigiu do lado dela em 09/11. Login e Minha Conta já mostram `gmail.com`.

## Resposta da Vono (09/11/2026)

A proposta nº 01234 (válida até 24/11) chegou por WhatsApp às 16:59 e só formaliza o contratado:
4 canais × R$ 50 + número R$ 32,90 = R$ 232,90/mês, adesão zero, pré-pago com recarga mínima de
R$ 25. Contato comercial: Alan Costa, gerente de contas, alan.costa@grupovono.com.br,
+55 31 92004-7088. Suporte técnico 24×7 por trás dele.

Perguntas do doc 17 §5 (item 1 do B30) feitas pelo WhatsApp e respondidas em três áudios às
17:26, 17:28 e 17:29 (transcrição automática, revisada; áudios guardados no WhatsApp do Daniel):

- **O uso cabe nas condições gerais?** Sim, "fica tranquilo": central de uma rede de telefones
  fixos de crianças ligando para os celulares cadastrados da família cabe no SIP Trunk Ilimitado,
  desde que não exceda a minutagem da cláusula 20.7 e **não use discador** (rajadas de muitas
  ligações por minuto). Sem discador, "o serviço vai funcionar normalmente".
- **Os 5.000 minutos são por canal?** Sim, cada canal dá direito a 5.000 minutos (4 canais =
  20.000). O teto do portal (`REDE_VONO_CANAIS` × 5.000 × 0,8 = 16.000) está coerente.
- **Custo extra, entrada?** Nenhum. O valor é fixo; com o SIP Ilimitado o número "se torna
  ilimitado", só a mensalidade. Sem fidelidade; livre para portar o número para fora.
- **Portabilidade do (11) 5108-3530 da Nvoip?** Possível. Ver item 5 acima.
- **Cancelar o tronco Tarifado?** Pode. Ele vem por padrão com a compra do número e não impacta o
  Ilimitado se for excluído, ou pode ficar no painel.

Risco contratual do doc 17 (cláusulas 20.2, 20.5, 20.6) tratado: há confirmação do gerente de
contas, em áudio, de que o uso cabe. Os áudios ficam guardados no WhatsApp do Daniel; não se
pede confirmação em texto (decisão de 09/11).
