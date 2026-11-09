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
| 13:03 | **celular → (11) 5444-1774 funcionou**: 5 s, atendida, chamador identificado (a Vono manda `"55DDDnúmero"`, o 55 já era tratado), áudio nos dois sentidos ("perfeição") |

## Em aberto

1. ~~Entrada pelo número da Vono~~ resolvido às 13:03 (ver tabela).
2. Queda para a Nvoip: na ligação das 12:28 a perna Nvoip foi atendida e encerrou no mesmo segundo.
   Reproduzir com `dialplan set global VONO_ENDPOINT vono-x` (força CHANUNAVAIL) e rastreamento
   SIP ligado (`b30-debug.log`, `pjsip set logger on`); depois voltar com `VONO_ENDPOINT vono`.
3. Portal: página Celulares e e-mail de boas-vindas mostrando os dois números para salvar; teto
   por criança em minutos quando a saída é pela Vono; aba Uso com minutos por tronco
   (`CALL_TRONCO` ainda não é gravado em `call_logs`).
4. Trocar a senha do tronco no Meu Vono (apareceu em capturas de tela durante a contratação) e
   cancelar o tronco Tarifado se não tiver uso.
5. Portabilidade do (11) 5108-3530 da Nvoip para a Vono, para voltar a um número só.
