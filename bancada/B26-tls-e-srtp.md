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

## O que falta provar com aparelho real

1. Linha de teste em `exigida`: o aparelho recebe os parâmetros pelo GDMS e volta a registrar sozinho, agora por
   TLS (`ps_contacts.uri` com `transport=TLS`)? Se não voltar em dois minutos, religar o aparelho.
2. Ligação entre a linha de teste e outra linha, nos dois sentidos: completa, com áudio nos dois lados, e a
   central mostra SRTP na perna cifrada.
3. Ligação para o celular (9 + ID) e do celular para a criança continuam funcionando.
4. Voltar a linha para `nenhuma` e conferir que ela registra por TCP de novo (caminho de volta).
5. Só então: `flask sip-cifragem todas exigida`, `REDE_SIP_CIFRAGEM=exigida` no `portal.env`, fechar a TCP 5060
   no iptables e trocar a frase da página `/por-dentro`.

Não validamos o certificado no aparelho (P2311 e P2367 ficam no padrão, desligados): a cifra protege contra quem
escuta a rede, não contra quem consegue se passar pelo servidor. Ligar a validação exige apontar o aparelho para o
nome `telefonefixo.org` em vez do IP e testar se o GRP2601 confia na autoridade do Let's Encrypt.
