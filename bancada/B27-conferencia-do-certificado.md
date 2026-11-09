# B27 — O aparelho confere o certificado da central

Objetivo: fechar o que a B26 deixou aberto. Com TLS e SRTP a ligação é cifrada, mas o aparelho aceitava qualquer
servidor que respondesse no endereço da central. Aqui o aparelho passa a conferir a cadeia do certificado e o nome.

## Parâmetros (GRP2601 1.0.7.11; os mesmos números existem no HT80x)

| P-value | Nome na referência | O que faz |
|---|---|---|
| P2367 | Validate Certification Chain | só aceita certificado assinado por autoridade que o aparelho conhece |
| P2311 | Check Domain Certificates | o nome do servidor (P47) tem de estar no certificado (RFC 5922) |
| P47 | Primary SIP Server | precisa ser o nome (`telefonefixo.org:5061`), não o IP |

`P8502` (Load CA Certificates) ficou no padrão, 0: as autoridades que vêm no aparelho bastam. Não mexemos nele
porque pode valer também para a conexão do aparelho com o GDMS, que é o nosso caminho de volta.

## Teste com aparelho real (06/11/2026)

Linha de teste (GRP2601 do Daniel), em modo `exigida`. Cada passo foi um envio de P-values pelo GDMS, aplicado
pelo aparelho em cerca de 20 s, sem ninguém tocar nele. O registro foi lido em `ps_contacts`.

| Passo | Enviado | Esperado | Resultado |
|---|---|---|---|
| 1 | P2367=1, servidor ainda pelo IP | registra (se o aparelho confiar na autoridade) | **registrou** em 25 s, em conexão nova |
| 2 | P2311=1, servidor ainda pelo IP | não registra: o certificado não tem o IP | **parou de registrar** (3 min observados) |
| 3 | P47=`telefonefixo.org:5061` | registra | **registrou** em 20 s |
| 4 | P2311=0, P2367=0, P47 = servidor falso | aceita o falso (é o risco de antes) | **aceitou**: TLS completo e enviou REGISTER ao falso |
| 5 | P2367=1, P47 = servidor falso | recusa o falso | **recusou**: abre a conexão, vê o certificado, fecha sem enviar nada; tenta de novo a cada 21 s |
| 6 | P47=`telefonefixo.org:5061`, P2311=1, P2367=1 | registra | **registrou** em 20 s |

O servidor falso foi um programa neste computador, na mesma rede do aparelho, com certificado autoassinado no
nome `telefonefixo.org`. Ele só anota o resultado do aperto de mão e o método da primeira mensagem, nunca o
conteúdo.

O que o teste mostra:

- O GRP2601 confia na cadeia atual do Let's Encrypt (folha ECDSA, YE1, Root YE, ISRG Root X2, ISRG Root X1; a
  central entrega os quatro) sem carregar autoridade nenhuma.
- A conferência da cadeia acontece depois do aperto de mão: do lado do servidor falso o TLS completa, mas o
  aparelho não envia o REGISTER. Não vaza o ID da linha nem a resposta da senha.
- A conferência do nome funciona e depende do P47: com o IP, o aparelho fica sem registro. Por isso o nome e as
  duas conferências têm de ir sempre juntos, na mesma configuração.

Não testado: só P2311=1 contra certificado autoassinado com o nome certo (em produção as duas vão juntas).

Depois, no mesmo dia, com a conferência ligada: ligação para o celular às 11h07 com áudio nos dois lados; aparelho
tirado da tomada e religado às 11h10, buscou a configuração no nosso servidor e registrou sozinho. As ligações
seguintes ficaram sem áudio num sentido por outro motivo, na central (`B28-audio-do-celular-e-jitterbuffer.md`).

Observação: o relógio do aparelho estava uma hora adiantado (fuso com horário de verão). Não atrapalhou a
conferência, que só falharia com o relógio fora da validade do certificado.

## Como ficou no código

- `REDE_SIP_CERT_NOME` (nome que está no certificado da porta TLS) e `REDE_SIP_CERT_LINHAS` (`todas`, ou IDs
  separados por vírgula num piloto) em `/etc/rede-aberta/portal.env`.
- `grandstream_xml.pvalues_linha(..., nome_certificado=)`: a linha que confere recebe P47 com o nome, P2311=1 e
  P2367=1; as outras recebem as duas em 0, de forma explícita. Vale para a configuração que o aparelho busca no
  nosso servidor e para o envio pelo GDMS (etapa `linha`), então as duas fontes nunca se contradizem.
- Job diário (`reconciliacao.verificar_certificado_sip`): confere o certificado servido na 5061 como o aparelho
  confere (cadeia e nome) e avisa por e-mail se falhar ou se faltarem menos de 15 dias. Com a conferência ligada,
  certificado vencido derruba os telefones; a renovação é automática (certbot e o gancho do `deploy/tls.sh`).

## Todas as linhas (06/11/2026, 12h40)

Com o sim do Daniel: `REDE_SIP_CERT_LINHAS=todas`, portal reiniciado e etapa `linha` enviada ao segundo aparelho.
Ele registrou em conexão nova, pelo nome e com as duas conferências, cerca de um minuto depois (o roteiro
desfaria tudo se ele não voltasse em 4 minutos). As cinco linhas ativas conferem, e as novas já nascem assim.
Para desfazer: voltar `REDE_SIP_CERT_LINHAS` no `portal.env`, reiniciar o portal e reenviar a linha
(`flask sip-cifragem <ID|todas> exigida`).

## Relógio do aparelho

No fuso automático o GRP2601 aplica ao Brasil a regra antiga de horário de verão e fica uma hora adiantado de
novembro a fevereiro. A configuração passou a mandar fuso fixo (`grandstream_xml.pvalues_relogio`: P64=customize,
P246=`UTC+3`, P143=0), calculado de `REDE_TIMEZONE`. Enviado à linha de teste pelo GDMS em 06/11; os outros
aparelhos recebem na busca diária de configuração. O Daniel conferiu o visor da linha de teste: hora certa.


09/11/2026: o fuso deixou de ser global. Cada família tem o seu (`familias.fuso`, sugerido pelo navegador no
cadastro e trocável em /fuso); `pvalues_relogio` gera o texto POSIX também para fuso com horário de verão
(famílias fora do Brasil). Mudança de fuso vai ao aparelho pelo GDMS (etapa `relogio` da fila); `REDE_TIMEZONE`
ficou só como padrão. Conferência pelo IP de onde o telefone busca a configuração (base GeoLite2 no servidor,
`deploy/geoip.sh`): divergência abre o caso `fuso_divergente` no painel.