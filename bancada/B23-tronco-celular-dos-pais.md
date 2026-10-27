# B23 — Tronco para o celular dos pais (planejado em 2026-10-26)

Objetivo: provar, sem app, que o telefone da criança alcança o celular do responsável e que o
celular do responsável alcança o telefone da criança. Decisão de produto em `docs/08`, item 6(c).

## O que o teste prova

1. Telefone do jose disca `9` + o próprio ID → o celular do Daniel toca, como ligação comum,
   vinda do número fixo do tronco.
2. Daniel liga do celular para o número fixo do tronco → o telefone do jose toca, porque o
   celular do Daniel está cadastrado como número da família. Número desconhecido não toca.

Fora do teste: cobrança, saldo por família, Pix, questão Anatel.

## Operadora para o teste

Uma conta só, em nome do Daniel (faz o papel da ONG). Nenhuma outra família abre conta.

Pesquisa de 26 e 27/10 nos sites, com navegador real onde o site bloqueava robôs:

| Operadora | Modelo | Celular/min | Número para receber | Cadastro | Conta SIP para Asterisk | Situação |
|---|---|---|---|---|---|---|
| **Nvoip** (Juiz de Fora, autorização Anatel no rodapé) | plano Free sem mensalidade; ligações por crédito pré-pago; número virtual com ativação + mensalidade (valor só no painel) | "a partir de R$ 0,05"; tabela do site não carregou | sim, por DDD | só nome, e-mail e senha em `painel.nvoip.com.br/signup` | sim: provisionador oficial no GitHub (`Nvoip/nvoip-pabx-provisioner`), servidor `sip.nvoip.com.br`, registro com usuário e senha, UDP 5060, ulaw/alaw | **escolhida** |
| Voipi | R$ 25/mês com número e conta SIP | R$ 0,35 | incluso | `app.voipi.com.br/cadastro` responde "Painel Nvoip: endereço não configurado" | seria revenda da Nvoip | **não opera**; descartada em 27/10 |
| BRVOZ | pré-pago, recargas de R$ 10 a 8.000 | R$ 0,23 | DID R$ 28/mês | loja: "para criar conta, faça um pedido"; produtos VoIP "fora de estoque" em 26 e 27/10 | sim | reserva fraca |
| FaleMais pré-pago | sem mensalidade, recarga mínima R$ 30 | R$ 0,28 (2019) | **não recebe** | pessoa física, cartão e boleto | não informa | só saída |
| Diskfree, Voipmundo | pacotes e planos para empresa, preço por contato | não publicam | sim, sem preço | formulário | sim | descartadas para a bancada |
| Telnyx (EUA) | por minuto, número US$ 1/mês | não encontrado para o Brasil | pessoa física com CPF, documento e comprovante de endereço, até 3 dias úteis | cartão em dólar | sim, bem documentado | reserva |
| Twilio (EUA) | por minuto, número US$ 4,25/mês | US$ 0,0663 | **só empresa com CNPJ** | cartão em dólar | sim | descartada para a bancada |

Visto no painel em 27/10 (conta gratuita, saldo zero): número virtual SP R$ 39,00/mês + R$ 59,00 de
ativação única (R$ 98 no primeiro mês); pagamento por saldo, cartão, boleto ou **Pix**; base de
conhecimento `suporte.nvoip.com.br/portal/pt/kb/manuais-tecnicos`, categoria PABX's, artigo "Como
integrar a Nvoip com 3CX, Asterisk, FreePBX, Issabel e Fusion PBX": o painel tem um card por PABX e,
ao abrir "Asterisk", mostra usuário, senha SIP e domínio `app.nvoip.com.br` (o provisionador no
GitHub usa `sip.nvoip.com.br`; testar os dois). Nada no artigo exige plano pago.

O que ainda não se sabe da Nvoip: preço mensal do número virtual, formas
de pagamento do crédito (Pix?), se o plano Free libera tronco SIP ou se exige plano pago, e se o
cadastro pede CPF ou CNPJ depois do primeiro acesso.

## Passo a passo do Daniel

1. Criar a conta em `painel.nvoip.com.br/signup` (nome, e-mail, senha). Não pagar nada ainda.
2. Dentro do painel, anotar o que aparece nos menus de **Tronco SIP** (ou "PABX", "Integração",
   "Ramais"), **Número virtual** (preço mensal e ativação) e **Créditos** (formas de pagamento). Se o
   cadastro pedir CPF ou CNPJ, usar o CPF. Se exigir CNPJ ou plano pago para o tronco, parar e avisar.
3. Se houver tronco SIP: criar um, e gravar usuário e senha em `~/.config/rede-aberta/bancada.env`
   (chmod 600), nunca no chat nem no git:
   `TRONCO_SERVIDOR=app.nvoip.com.br` (o que o card mostrar), `TRONCO_USUARIO=...`, `TRONCO_SENHA='...'`.
4. Contratar um número virtual com DDD 11 e gravar em `TRONCO_NUMERO=11XXXXXXXX`. Apontar o número
   para o tronco, se o painel perguntar.
5. Colocar R$ 30 de crédito.
6. Avisar aqui que está pronto e qual celular vai ser o "número da família".

## Passo a passo do Claude (depois do 5)

1. Asterisk da bancada: `pjsip` com registration + auth + endpoint para a Nvoip, no molde do
   provisionador oficial (UDP 5060, ulaw/alaw, `from_user` = usuário, `direct_media=no`,
   `rtp_symmetric`, `force_rport`, `rewrite_contact`, `identify` por `sip.nvoip.com.br`).
2. Dialplan: `_9XXXXXX` → busca em `familia_telefones` o número cadastrado para a criança dona do
   ID discado → `Dial(PJSIP/0<ddd><numero>@nvoip, 60, L(1800000))` (formato do número a confirmar no painel) com limite de tempo.
3. Dialplan de entrada: chamada que chega pelo tronco → compara `CALLERID(num)` normalizado com
   `familia_telefones` → toca no(s) telefone(s) das crianças daquela família; número desconhecido
   recebe mensagem curta e desliga.
4. Tabela nova `familia_telefones` (familia_id, numero E.164, apelido, criado_em) e tela no site
   "Telefones da família" (máximo 3 números). No teste, pode ser inserido por SQL.
5. Registrar aqui: hora, CDR das duas ligações, qualidade de áudio relatada, custo debitado.

## Execução (27/10)

| hora | evento |
|---|---|
| 10:34 | conta Nvoip criada (nome, e-mail, senha; sem CPF/CNPJ) |
| 11:17 | número virtual (11) 5108-3530 contratado: R$ 39/mês + R$ 59 ativação; assistente do painel: PABX > Asterisk > "Direcionar para usuário" 15XXXXXXX, BINA do tronco = o número |
| 11:08 | card Asterisk em Integrações mostra usuário SIP, senha e domínio `app.nvoip.com.br`; botão "Integrar" não responde (irrelevante) |
| ~11:30 | saldo colocado pelo Daniel |
| 12:0x | `deploy/tronco.sh` na bancada: tabela `familia_telefones`, `pjsip_tronco.conf` (registro + auth + aor + endpoint + identify), `sorcery.conf` com fonte `config` antes do `realtime`, dialplan 9+ID e `[tronco-entrada]`, AGI `check_entrada.py`, som `sem-celular`, `REDE_TRONCO_NUMERO` no portal.env |
| 12:0x | `pjsip show registrations`: **nvoip-reg Registered (exp. 267s)**; qualify do contato `app.nvoip.com.br` 11 ms; os dois GRP re-registraram após o restart |
| 12:0x | celular do Daniel cadastrado como "Pai" nas duas famílias dele (SQL; a tela `/celulares` do site faz o mesmo) |

Aprendido no caminho:
- `app.nvoip.com.br` e `sip.nvoip.com.br` resolvem para o mesmo IP (54.233.253.44 + AAAA). Servidor sem IPv6: PJSIP usa o A.
- Com `sorcery.conf` apontando só para `realtime`, o `pjsip.conf` é ignorado para endpoint/auth/aor/identify. Foi preciso acrescentar `config,pjsip.conf,criteria=type=...` antes de cada linha realtime. `sorcery.conf` só é lido na carga do módulo: `systemctl restart asterisk`, não basta `pjsip reload`.
- O papel `portal` não tem REFERENCES nas tabelas de `postgres`: tabela nova com chave estrangeira é criada no SQL do deploy, não pelo `flask init-db`.
- Dupla gravação no histórico: o dialplan antigo grava no `h` e depois do `Dial`; nas extensões novas, `CALL_DEST` é limpo depois de gravar.

| 11:44 a 11:49 | **9+ID funcionou**: três ligações 7XX534 → 9736534 (8 s, 29 s, 17 s), celular mostrou (11) 5108-3530. Na primeira, áudio só num sentido (ver abaixo); nas seguintes, nos dois |
| 12:02 e 12:03 | celular → (11) 5108-3530: INVITE chegou da Nvoip (54.233.253.44), identificado como endpoint `nvoip`, mas `check_entrada` bloqueou e tocou "número inválido". Causa: a Nvoip manda o chamador no display name do From e no `P-Asserted-Identity`; o From user é o nosso usuário 15XXXXXXX |
| 12:2x | correção: AGI recebe `CALLERID(name)`, `P-Asserted-Identity` e `Remote-Party-ID` como argumentos e usa o primeiro que for número nacional; redeploy |
| 12:3x | **celular → telefone do jose funcionou**: tocou mostrando "Pai", áudio nos dois sentidos |

Cabeçalhos que a Nvoip envia na entrada (para referência): `From: "11987654321" <sip:15XXXXXXX@172.31.x.x>`,
`P-Asserted-Identity: "11987654321" <sip:11987654321@...>`, `X-NUMBERSIP: 11987654321`, `X-URADID: 551151083530`,
`Privacy: none`; Request-URI com `;line=...` (casa com a nossa registration `line=yes`). SDP oferece PCMA, G729, telefone-event.

Áudio num sentido só na primeira 9+ID: o log mostra `dropping due to strict RTP protection ... Will switch` para
pacotes do GRP (191.32.207.123:37512). O GRP mudou a porta de origem do RTP no meio (NAT doméstico) e o Asterisk
levou alguns segundos para aceitar a nova origem. Não se repetiu. Se voltar, opções: `strictrtp=seqno` ou
`rtp_keepalive` no endpoint do GRP. Fica anotado, não bloqueia.

Scanners SIP: durante a captura chegaram INVITEs de 5.196.115.99 e 160.119.76.169 para destinos internacionais
(+972..., 0000011442...). Foram recusados (401). Com tronco pago ligado, isso vira risco real: fail2ban para o
Asterisk e, se possível, limitar 5060 às origens conhecidas (GRPs vêm de IPs dinâmicos, então só fail2ban +
senhas fortes + `allow_unauthenticated_options=no`). Abrir como item de operação.

## Resultado

**Provado nos dois sentidos, sem app, em um celular comum.** 9+ID do telefone da criança toca nos celulares
cadastrados da família com o número fixo da rede como identificador; o celular cadastrado ligando para o
número fixo faz tocar o telefone da criança com o apelido ("Pai"); número não cadastrado ouve "número
inválido". Custo do teste: R$ 98 (número, 1º mês) + minutos do saldo. Fica em aberto o modelo de cobrança
(doc 08, item 6c) e a questão Anatel.

Ajuste pedido pelo Daniel depois do teste (27/10, 12:40): em vez de todos os celulares tocarem juntos,
um jeito de discar para cada um. 9+ID = celular 1, 8+ID = celular 2, máximo dois por família (são os
únicos prefixos livres: 0 é grupo, 1 é serviço, 2 a 7 começam os IDs). A página Celulares mostra a
posição e troca a ordem; o cartão da criança imprime "Mãe (celular) 9736534#" e "Pai (celular) 8736534#".
Coluna `posicao` em `familia_telefones`. Terceiro caminho, sem prefixo: teclas rápidas "Mãe"/"Pai" no
GRP2601, quando o B21 fechar.

Código: `rede/servicos/familia_telefones.py`, `chamadas.decidir_familia`, `agi/check_entrada.py`,
`[tronco-entrada]` e `_[89][2-7]XXXXX` em `extensions.conf`, `deploy/tronco.sh`, tela `/celulares`.
Testes em `tests/test_familia_telefones.py`.
