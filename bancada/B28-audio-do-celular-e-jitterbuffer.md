# B28 — A criança não ouvia o celular: amortecedor de voz na perna da operadora

## Sintoma (06/11/2026)

Ligação do telefone para o celular da família (9 + ID): o celular ouvia a criança, a criança não ouvia o celular.
Quatro ligações seguidas assim (11h22, 11h23, 11h30, 11h37). A das 11h07 tinha funcionado. A central não
registrou aviso nem erro em nenhuma.

Apareceu logo depois de o aparelho ser religado no teste da B27, mas não tem relação com ele: a negociação da
chamada estava certa (uma linha de áudio, `sendrecv`, cifra `AES_CM_128_HMAC_SHA1_80` aceita pelos dois lados).

## Onde a voz parava

Contagem de pacotes de voz por trecho (ligação de 30 s), sem gravar conteúdo:

| Trecho | Pacotes |
|---|---|
| telefone para a central | cerca de 1.500 |
| central para a operadora | cerca de 1.500 |
| operadora para a central | cerca de 1.600 (começa antes do atendimento: a operadora manda o toque de chamada) |
| central para o telefone | 2 (na ligação seguinte, 5), todos no instante do atendimento |

`pjsip show channelstats` confirmou: canal do tronco recebendo normalmente, canal do telefone com 2 a 5 pacotes
transmitidos. Os dois canais em `sendrecv`, com transcodificação montada (ulaw, slin16, g722).

Entre a leitura do tronco e a escrita no telefone só há o que o `b(set-jitterbuffer^s^1)` instala na perna do
tronco: `JITTERBUFFER(adaptive)=200,1000,40` e `VOLUME`.

## Mudança

`extensions.conf`: nas ligações da criança para o celular, a perna do tronco passa a usar `set-volume-tronco`
(só o volume, sem `JITTERBUFFER`). O amortecedor do lado da criança continua, e o telefone tem o dele. As
ligações entre crianças e as que chegam do celular não mudaram. Aplicado com `dialplan reload`, sem reiniciar.

## Prova

| Passo | Resultado |
|---|---|
| Telefone para o celular, depois da mudança (12h34, 12 s) | **áudio nos dois lados**, conferido pelo Daniel |
| Celular para o número fixo (12h34, 7 s) | **áudio nos dois lados**, conferido pelo Daniel |
| Telefone para o celular, de novo (13h08, 8 s) | **áudio nos dois lados**, conferido pelo Daniel |

## O que isto prova e o que não prova

- Prova que o defeito estava dentro da central, entre o tronco e o telefone, e que sem o amortecedor nessa perna
  a ligação voltou a ter áudio.
- A explicação do mecanismo é hipótese: a operadora manda áudio antes do atendimento e troca de fluxo quando o
  celular atende; o amortecedor adaptativo deixaria passar os primeiros quadros (os 2 a 5 pacotes) e seguraria o
  resto. Não medimos os carimbos de tempo do RTP para confirmar.
- Foram duas ligações boas depois de quatro ruins. Como o defeito era intermitente (11h07 funcionou; na B26 uma
  captura mostrou metade da voz), vale observar as próximas ligações para celular.
- As medições detalhadas (contagem por canal) já tinham expirado na hora da ligação de prova; o resultado vem do
  relato de quem ligou e do `call_logs`.

## Como medir de novo

- `tcpdump -n -tt -i any udp portrange 10000-20000`, contando por sentido em blocos de 10 s (o IP público do
  telefone não está em `ps_contacts.via_addr`, que guarda o IP da rede da casa).
- `asterisk -rx "pjsip show channelstats"` durante a ligação: Receive e Transmit de cada canal.
- Nunca ligar `pjsip set logger` nem depuração do `res_srtp` em arquivo sem filtrar: os dois escrevem as chaves
  da ligação.
