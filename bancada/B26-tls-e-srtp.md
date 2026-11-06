# B26 — SIP por TLS e voz por SRTP

Objetivo: cifrar o trecho entre o telefone e a central. Até 05/11/2026 o SIP ia por TCP na 5060 e a voz por RTP,
os dois sem cifra.

## O que está pronto (05/11/2026)

- **Central** (`portal/deploy/tls.sh`): `transport-tls` na 5061 com o certificado Let's Encrypt do site, copiado
  para `/etc/asterisk/keys` e recopiado a cada renovação (gancho do certbot, que também recarrega o PJSIP).
  Criado com `module reload res_pjsip.so`, sem reiniciar: os telefones continuaram registrados. Porta aberta no
  iptables e num NSG da Oracle preso só a esta máquina. De fora, `openssl s_client` na 5061 mostra o certificado
  do site. `res_srtp.so` já estava carregado.
- **Portal**: cada linha tem um modo, guardado no próprio ramal (`ps_endpoints`):

  | Modo | Central (`criancas.CIFRAGENS`) | Aparelho (`grandstream_xml.pvalues_linha`) |
  |---|---|---|
  | nenhuma | `transport-tcp`, sem SRTP | P130=1 (TCP), P183=0 |
  | transicao | sem transporte fixo, `media_encryption=sdes`, `media_encryption_optimistic=yes` | P130=2 (TLS), servidor com `:5061`, P2329=0, P183=1 |
  | exigida | igual, com `media_encryption_optimistic=no`: sem SRTP a ligação não completa | P130=2, `:5061`, P2329=0, P183=2 |

  `flask sip-cifragem <ID|todas> <modo>` muda a central na hora e manda os parâmetros da linha ao aparelho pelo
  GDMS (etapa `linha` da fila, sem senha nenhuma dentro). Linhas novas nascem no modo de `REDE_SIP_CIFRAGEM`.

## Teste com aparelho real (05/11/2026, noite)

Uma linha de teste (GRP2601 do Daniel) passou para `exigida` com `flask sip-cifragem`.

| Passo | Resultado |
|---|---|
| Aparelho recebe os parâmetros pelo GDMS e volta a registrar sozinho | **sim**: fila do minuto enviou em cerca de 50 s; registro por TLS 65 s depois do comando, sem ninguém tocar no aparelho |
| Criança liga para o celular (9 + ID) | **sim**: completou, áudio nos dois lados |
| Celular liga para o número fixo e toca a criança | **sim**, duas vezes: completou, áudio nos dois lados |
| Voz cifrada no trecho do telefone | **sim**: pacotes de voz de 182 bytes nos dois sentidos (172 do RTP mais 10 da autenticação do SRTP); no trecho da operadora, 172 bytes, sem cifra, como esperado |
| Volta para `nenhuma` | **sim**: registro por TCP 65 s depois |
| De novo `exigida` | **sim**: registro por TLS 65 s depois |
| Ligação entre duas crianças com a linha cifrada | **pendente**: o segundo aparelho não estava à mão |

Como conferir a cifra sem ver segredo nenhum: `tcpdump -n -i any udp portrange 10000-20000` e olhar o tamanho.
Com G.722 ou PCM de 20 ms, 172 bytes é RTP sem cifra e 182 é SRTP. Na última ligação (19 s) os quatro sentidos
tiveram a mesma contagem de pacotes, cerca de 950.

Observação: na primeira captura, somada sem separar por tempo, a central parecia ter enviado ao telefone metade da
voz esperada. O Daniel confirmou áudio nos dois lados e a captura seguinte, em blocos de 10 segundos, fechou a
conta. Para a próxima vez, capturar sempre por blocos de tempo.

## O que falta

1. Ligação entre duas crianças, nos dois sentidos, conferida por quem estiver com os aparelhos.

## Migração de todas as linhas (05/11/2026, 21h10)

Com o sim do Daniel: a segunda linha com aparelho passou para `exigida` e registrou por TLS em 57 s, sozinha (o
roteiro devolveria a linha ao modo antigo se ela não voltasse em 4 minutos). As linhas sem aparelho conectado
passaram para `exigida` só na central. Depois, `FECHAR_TCP=1 deploy/tls.sh`: `REDE_SIP_CIFRAGEM=exigida` (linhas
novas já nascem cifradas), TCP 5060 fechada no iptables e conferida de fora. Dois minutos depois os dois aparelhos
tinham renovado o registro por TLS e o tronco da operadora (UDP) seguia registrado. A página `/por-dentro` passou
a dizer que a ligação entre o telefone e o servidor é cifrada.

Não validamos o certificado no aparelho (P2311 e P2367 ficam no padrão, desligados): a cifra protege contra quem
escuta a rede, não contra quem consegue se passar pelo servidor. Ligar a validação exige apontar o aparelho para o
nome `telefonefixo.org` em vez do IP e testar se o GRP2601 confia na autoridade do Let's Encrypt.

Feito em 06/11/2026 na linha de teste: `B27-conferencia-do-certificado.md`.

Em 06/11/2026 às 6h29 o Asterisk reiniciou sozinho (atualização automática de segurança do sistema). O
`transport-tls` subiu da configuração e os dois aparelhos voltaram a registrar por TLS sem ninguém mexer.
