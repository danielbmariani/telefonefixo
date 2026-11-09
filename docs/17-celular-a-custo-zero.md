# 17. Ligar para celulares a custo quase zero: pesquisa e alternativas

Pesquisa feita em 07/11/2026 a pedido do Daniel. Metas que ele fixou: (1) o pai só registra o
telefone; (2) o pai paga no máximo R$ 5 por mês, de preferência nada, e a criança pode falar ao
menos 5 horas por mês; (3) rede de mais de mil crianças; (4) o projeto gasta no máximo R$ 1.000
por mês com isso; (5) até R$ 20 mil para montar. A solução atual (Nvoip por minuto, R$ 0,30 o
minuto para celular, orçamento de R$ 500) foi considerada subótima. Preços vistos nos sites no
dia; fontes no fim.

## 0. Resposta curta

Por minuto não fecha em nenhuma operadora do mundo: mil crianças falando 5 horas são 300 mil
minutos por mês, e o teto de R$ 1.000 exige R$ 0,003 por minuto, abaixo até da tarifa de
interconexão que a Anatel fixa entre operadoras (R$ 0,015 a 0,031 em 2023). Só três coisas cabem
no orçamento, e elas se combinam:

1. **Inverter quem liga (retorno automático).** Todos os planos de celular do Brasil, até o
   Prezão de R$ 15, já incluem ligações ilimitadas para qualquer número. O minuto que o pai
   origina já está pago. A criança disca 9+ID, a central dá um toque no celular do pai (ligação
   não atendida, sem custo) e o pai retorna para o número fixo da rede, cuja entrada é grátis na
   Nvoip. A central reconhece o número do pai, encontra a criança esperando e junta os dois.
   Custo por minuto: zero. Dá para montar esta semana, sem contrato novo. O pai precisa fazer uma
   coisa: salvar o número da rede nos contatos (os celulares bloqueiam desconhecidos, como se viu
   em 05/11) e retornar a ligação, como se "dava um toque" nos anos 2000.
2. **Canais ilimitados em vez de minutos.** A Vono vende canal SIP com ligações ilimitadas para
   fixo e celular de todo o Brasil por R$ 50 o canal (R$ 40 de 9 a 20 canais), sem fidelidade,
   sem ativação e aceitando CPF. Dez canais custam R$ 400 por mês e atendem mil crianças que
   falem 30 minutos por mês cada, com o celular do pai tocando direto, sem o pai fazer nada. O
   limite é 5.000 minutos por canal por mês; quando a rede encostar nele, o retorno automático
   assume o excedente.
3. **WhatsApp como telefone dos pais, sem app novo.** A API de chamadas do WhatsApp fala SIP
   direto com o Asterisk. Ligação iniciada pelo pai é grátis, sem limite; ligação iniciada pela
   central custa R$ 0,0556 o minuto, com teto de 100 chamadas conectadas por dia por número. O
   número do WhatsApp pode ser o próprio fixo da rede. Exige limite de 2.000 mensagens por dia,
   que vem com a verificação da empresa (CNPJ) ou com volume de mensagens. Fica para quando
   houver CNPJ ou base grande.

**Recomendação:** começar pelo retorno automático na Nvoip (custo zero, prova em dias), contratar
1 canal da Vono para provar a ligação direta e medir o uso real do piloto por dois meses, e
dimensionar os canais pelo uso medido. Com mil crianças e 30 a 60 minutos por criança, a conta
fica entre R$ 450 e R$ 700 por mês (canais + número), dentro do teto. Os pais não pagam nada.
Não cobrar os R$ 5: cobrar por ligação é revenda de telefonia, que exige outorga da Anatel; se um
dia houver cobrança, que seja contribuição associativa da ONG, sem relação com minutos.

**Decisão do Daniel (07/11/2026):** o retorno automático (A) está **descartado**, por exigir que o
pai retorne a ligação ("não é sem fricção suficiente"). Caminho principal: canais ilimitados da
Vono (B), com o WhatsApp (C) quando houver CNPJ. A prova do retorno automático (B29) sai do plano; a da Vono (B30) vira a primeira.

## 1. O problema em números

Custo por minuto para celular, visto em 07/11/2026:

| Quem | R$/min para celular | Observação |
|---|---|---|
| Interconexão (VU-M, Anatel, 2023) | 0,015 a 0,031 | piso do mercado; o que uma operadora paga à outra |
| Vono canal ilimitado | 0,008 a 0,013 efetivo | R$ 40 a 50 por canal, teto 5.000 min/canal/mês |
| WhatsApp Calling, iniciada pela central | 0,0556 | R$ por minuto, pulsos de 6 s; iniciada pelo pai é grátis |
| Zadarma (Rússia/Bulgária, número BR) | ~0,16 | US$ 0,03; entrada grátis |
| Nvoip (atual) | ~0,30 | estimado; fatura real ainda não vista |
| Twilio | ~0,37 | US$ 0,066; só CNPJ |

Dimensionamento para 1.000 crianças (Erlang B, 1% de bloqueio, 25% do tráfego do dia na hora de
pico):

| min/criança/mês | min/mês da rede | canais no pico | canais pelo teto de 5.000 | Vono R$/mês | Nvoip R$/mês | WhatsApp R$/mês |
|---|---|---|---|---|---|---|
| 15 | 15.000 | 7 | 3 | 315 | 4.500 | 834 |
| 30 | 30.000 | 10 | 6 | 400 | 9.000 | 1.668 |
| 60 | 60.000 | 16 | 12 | 640 | 18.000 | 3.336 |
| 120 | 120.000 | 26 | 24 | 910 | 36.000 | 6.672 |
| 300 (5 h) | 300.000 | 55 | 60 | 1.800 | 90.000 | 16.680 |

Leitura: canais ilimitados cabem no orçamento até cerca de 120 minutos por criança por mês. As
5 horas por criança são um direito, não a média esperada: ligações de criança para mãe são curtas
("posso ir na casa do João?"). O que não cabe nos canais vai pelo retorno automático, que custa
zero. Piloto de 100 crianças: 3 canais (R$ 150) atendem 30 min/criança; 10 canais (R$ 400)
atendem 5 h/criança.

A média real ainda não foi medida. É o número mais importante a coletar no piloto.

## 2. Como os outros fazem

Todos os "telefones fixos para crianças" dos EUA cobram mensalidade para falar com números
comuns, e nenhum tem opção gratuita para fora da rede:

| Produto | Aparelho | Dentro da rede | Para celulares comuns |
|---|---|---|---|
| Tin Can (Party Line) | US$ 100 | grátis | US$ 9,99/mês; 85% dos clientes assinam |
| Pinwheel Home (jul/2026) | US$ 68 | grátis | US$ 6,99/mês até 5 números; US$ 9,99 ilimitado |
| Ooma MyPhone (mai/2026) | varia | não há plano grátis | US$ 7,99/mês |
| Ring Ring | US$ 75 a 89; "Bridge" US$ 59 para telefone analógico próprio | grátis | US$ 8,95/mês |
| Voiply | US$ 55 a 75 | | US$ 8,95/mês |

Nenhuma publica a operadora por trás (a Tin Can não diz se usa Twilio ou Bandwidth). O modelo é o
mesmo: rede fechada de graça, saída para a rede pública por assinatura, porque nos EUA o minuto
terminado em celular custa menos de US$ 0,01 e sobra margem. Duas ideias da Tin Can valem
registro: "shared line" (vários aparelhos dividem um número; útil para irmãos) e Pinwheel
limitando a 5 números aprovados, que é exatamente o pedido do Daniel.

O que muda no Brasil, a nosso favor: aqui o pai já tem ilimitado para fixo no plano dele, e a
entrada em número virtual é grátis. Logo a direção pai → rede custa zero para todo mundo, e o
retorno automático transforma a direção criança → pai nessa mesma direção. Nenhum dos produtos
americanos faz isso porque lá o plano do pai não é universalmente ilimitado.

"CanPhone" não existe como produto; os resultados apontam para a Tin Can, já estudada em
`docs/12`.

## 3. As alternativas, uma a uma

Critérios: custo por mês para 1.000 crianças, o que o pai precisa fazer, risco (contrato, Anatel,
imagem), esforço de implementação.

### A. Retorno automático ("toque" + entrada grátis)

**Como funciona.** A criança disca 9+ID. A central (1) registra uma pendência "criança X espera o
celular Y", (2) disca para o celular do pai pela Nvoip e desliga antes de atender, após 4 a 5
segundos de toque, e (3) toca para a criança uma mensagem curta ("estou chamando sua mãe, espere
na linha") seguida de música. O pai vê a chamada perdida do número da rede, salvo como "Telefone
Fixo", e retorna; o plano dele cobre. A ligação entra pelo `[tronco-entrada]`, o AGI reconhece o
número do pai, acha a pendência e junta as duas pontas sem tocar de novo no telefone da criança.
Se o pai não retorna em 90 segundos, a criança ouve "sua mãe não retornou ainda; quando ela
ligar, seu telefone toca" e desliga; a pendência fica mais 10 minutos para que o retorno tardio
toque direto no telefone da criança.

**Custo.** Zero por minuto. A Nvoip não cobra recebimento em número virtual ("você paga só a
mensalidade e recebe ilimitado"). Ligação não atendida não gera minuto; confirmar no CDR do painel
na primeira semana (a Nvoip não publica isso por escrito). O número virtual recebe 5 chamadas
simultâneas; mais do que isso é pacote de 5 canais adicionais, preço só no painel. Com 1.000
crianças e 30 min/criança, o pico é de 4 a 5 chamadas simultâneas; a partir daí, 1 a 2 pacotes.

**O que o pai faz.** Salva o número da rede nos contatos (já é obrigatório para o celular tocar) e
retorna a chamada perdida. É o mesmo gesto do "dar um toque" que todo adulto brasileiro conhece.
Variante com menos atrito: enviar junto um SMS "José está te chamando. Ligue para (11) 5108-3530"
(a Nvoip e outras cobram R$ 0,05 a 0,10 por SMS; com 10 ligações por criança por mês dá R$ 500 a
1.000, então só se o toque sozinho não bastar).

**Riscos.** Pai que não entende o toque na primeira vez (resolve com a página Celulares e o e-mail
de boas-vindas); celular com "silenciar desconhecidos" (já é problema hoje); spoof do número do
pai por terceiros para falar com a criança (mitigação: a pendência só dura minutos e só aceita o
número que a criança chamou; PIN opcional para quem quiser). Nada de Anatel: a família usa o
próprio plano.

**Esforço.** Baixo. Tabela `chamadas_pendentes` (criança, telefone, criado_em, estado), ajuste no
contexto `_[89][2-7]XXXXX` (Dial com timeout curto e sem atender, depois Playback + MusicOnHold +
espera por evento), ajuste no `check_entrada.py` para olhar pendências antes de tocar no telefone
da criança, dois áudios Piper. Teste real obrigatório pela regra de `call_logs`.

### B. Canais ilimitados (Vono)

**Oferta.** Vono "SIP Trunk Ilimitado": ligações ilimitadas para fixo e celular de todo o Brasil,
sem fidelidade, ativação grátis, numeração em 67 DDDs. Preço por canal por mês: R$ 50 (1 a 4
canais), R$ 45 (5 a 8), R$ 40 (9 a 20), R$ 35 (21 a 30), R$ 30 (31 ou mais); a faixa vale para
todos os canais. Pesquisa de 05/11 já tinha visto que aceita CPF. Condições gerais: o "ilimitado"
é limitado a 5.000 minutos por canal por mês (20.7), revenda e call center são proibidos (20.2,
20.6) e a interpretação fica com a Vono (20.5).

**Custo.** R$ 400 por mês (10 canais) para mil crianças com 30 min/criança; R$ 640 (16 canais)
com 60 min. Comparação: Nvoip "Ligar Ilimitado" custa R$ 99 por pacote e permite uma única
chamada simultânea, ou seja, 10 simultâneas = R$ 990; Vozio anuncia ilimitado "a partir de R$ 99"
sem publicar canais; Vivo Empresas cobra R$ 45 por canal, só CNPJ; AvoIP, R$ 599 por 10 canais
com 24 meses. A Vono é a mais barata e a única com CPF e sem fidelidade.

**O que o pai faz.** Nada além de cadastrar o número. O celular toca com o número da rede, como
hoje.

**Riscos.** O uso é "uma família ligando para si mesma", não call center nem revenda, mas quem
decide é a Vono. Antes de contratar, perguntar por escrito (modelo em §5): o uso cabe? os 5.000
minutos são por canal? o canal é bidirecional e a entrada é grátis? o tronco vem com número ou o
número é à parte? dá para portar o (11) 5108-3530 da Nvoip? aceita CPF? Guardar a resposta.
Operacionalmente: o portal já tem `servicos/custos.py`; trocar o teto em reais por teto em minutos
da rede (80% de 5.000 × canais) e manter o teto por criança. Quando encostar, desviar para o
retorno automático (A) em vez de recusar a ligação.

**Esforço.** Baixo. Segundo tronco no `pjsip_tronco.conf`, rota de saída preferindo Vono, Nvoip
como reserva, contador mensal de minutos por tronco.

### C. WhatsApp Calling (API oficial da Meta)

**Regras (documentação da Meta, lida em 07/11).**
- Chamada iniciada pelo usuário (pai liga para o número da rede no WhatsApp): **grátis**, em
  qualquer país. A chamada entra por SIP (TLS, mídia SRTP) no nosso Asterisk, com Opus ou G.711.
- Chamada iniciada pela empresa (central liga para o pai): R$ 0,0556 por minuto (fonte
  secundária em reais; US$ 0,0108 na tabela da Twilio), pulsos de 6 segundos. Exige permissão
  do usuário, que pode ser permanente (ele concede uma vez no perfil ou numa mensagem). **Teto de
  100 chamadas conectadas por 24 horas por número da empresa**; 4 chamadas seguidas não
  atendidas revogam a permissão.
- Mensagem com botão "Ligar" (`voice_call`): a central manda ao pai uma mensagem interativa
  "José quer falar com você" com um botão que abre a chamada de WhatsApp para a rede, grátis
  para os dois lados. A mensagem é categoria "utility" (centavos; grátis dentro da janela de 24 h
  de atendimento).
- Requisitos: número usado pela Cloud API (pode ser fixo, verificado por ligação de voz), limite
  de mensagens de 2.000 por dia. Portfólios novos começam em 250; sobe a 2.000 por verificação
  da empresa **ou** por enviar 2.000 mensagens de template entregues em 30 dias com boa
  qualidade. A verificação aceita CNPJ e certificado de MEI (CCMEI); não aceita CPF.

**Como ficaria.** O número do WhatsApp da rede é o próprio (11) 5108-3530. Criança disca 9+ID →
a central manda a mensagem com o botão "Ligar" e, se tiver permissão, também liga pelo WhatsApp
(R$ 0,0556/min) ou pelo canal Vono. O pai toca no botão (ou atende) e fala; o áudio chega por SIP
e a central junta com a criança. O pai liga para a criança pelo WhatsApp de graça a qualquer
hora, de qualquer país. Não instala nada: o WhatsApp já está no celular de praticamente todo
pai brasileiro, e toca com o app fechado (é a objeção de 26/10 aos apps, resolvida pela Meta).

**Custo.** Mil crianças, 30 min/criança, metade das ligações pela central: R$ 830 por mês; se
tudo for pelo botão "Ligar", só as mensagens (R$ 30 a 50). O teto de 100 chamadas conectadas por
dia por número obriga a usar o botão como caminho principal em escala, ou vários números.

**Riscos.** Dependência da Meta (preço e regras mudaram três vezes em 2025-2026); exige CNPJ ou
volume; dados do pai passam pela Meta (registrar nos termos e na página de privacidade); Opus e
SRTP no Asterisk (recompilar com `codec_opus`, `res_srtp`); a Meta diz que não dá para ponte com
a rede pública *pelo lado dela*, o que é outra coisa: a ponte é nossa, no Asterisk.

**Esforço.** Médio. Portfólio Meta, Cloud API, template aprovado, endpoint PJSIP TLS/SRTP, webhook
para permissões, tela "Receber pelo WhatsApp" na aba Celulares. Fica para quando houver CNPJ (MEI
custa R$ 82 a 87 por mês em 2026, mas a atividade precisa ser permitida) ou a rede tiver volume.

### D. Combinação recomendada

| Fase | Quando | Custo/mês (1.000 crianças, 30 a 60 min) | O pai faz |
|---|---|---|---|
| 1. Retorno automático na Nvoip | esta semana | R$ 39 (número) | salva o contato, retorna o toque |
| 2. Canais Vono para ligação direta; retorno como transbordo | após prova e 2 meses de medição | R$ 440 a 680 | nada |
| 3. WhatsApp para quem preferir e para pais fora do país | quando houver CNPJ | + R$ 50 a 200 | aceita uma vez no WhatsApp |

O portal decide a rota por ligação: canal Vono livre e abaixo do teto do mês → direta; senão →
retorno automático; pai com WhatsApp autorizado → botão "Ligar" junto. A criança nunca recebe
"sem minutos": no pior caso ouve "estou chamando sua mãe".

### E. Linha fixa residencial ilimitada + gateway FXO

Claro Fixo Brasil Ilimitado (fixo e celular de todo o Brasil) anunciado a partir de R$ 35/mês;
TIM Fixo Brasil Total Plus R$ 42 a 52 (via rede móvel, 12 meses); Vivo Fixo Ilimitado Brasil
R$ 83 a 99. Cada linha é um canal; a porta analógica do modem entra num gateway FXO (Grandstream
HT813, 1 porta, ~R$ 400; GXW4108, 8 portas, ~R$ 2.500) ligado ao Asterisk pela internet.

Custo por canal parecido com a Vono, mas pior em tudo o mais: linhas presas a um endereço (ou
espalhadas por casas de voluntários, o que vira operação), hardware, e os contratos residenciais
têm cláusulas de "uso pessoal" e "uso excessivo desproporcional à média" com rescisão (termos da
Claro de 2024; o MPF já obrigou a Claro a explicitar restrições de "ilimitado"; o Net Fone antigo
limitava a 1.000 minutos para celulares). Só vale como plano B se a Vono recusar o uso.

### F. Gateway celular com chips ilimitados ("chipeira")

Chips Controle com ligações ilimitadas custam R$ 50 a 60 por mês (Vivo 59, TIM 49,99, Claro
59,90) e um gateway VoLTE de 4 a 8 chips sai por R$ 3 a 10 mil (OpenVox VS-GW1202 chassi R$ 265
mais módulos; Khomp EBS 90 R$ 9,8 mil; Dinstar UC2000-VE-4 VoLTE ~R$ 3 mil importado, homologação
a conferir). Dezesseis chips dariam 16 canais por R$ 900 por mês.

**Não recomendo.** Os termos da Claro Controle proíbem expressamente "PABX, chipeiras, dentre
outros equipamentos"; a TIM "poderá, a seu exclusivo critério, suspender" e cancela a oferta; as
operadoras detectam por IMEI e padrão de uso e bloqueiam sem aviso. Com 2G e 3G em desligamento,
só gateway VoLTE homologado serve. E "chipeira" é a palavra do telemarketing e do golpe; não é
imagem para um projeto de crianças. Mesmo o uso só para receber (chips sem plano, entrada grátis)
tem o mesmo risco de bloqueio. Fica registrado como opção técnica, descartada por contrato e
imagem.

### G. Atacado e outras operadoras por minuto

Zadarma: número brasileiro US$ 6/mês, entrada grátis, celular US$ 0,03 (~R$ 0,16): metade da
Nvoip, ainda 50 vezes o necessário. Telnyx: não publica tarifa para celular no Brasil fora da
tabela logada. Twilio: US$ 0,066 e só CNPJ. Marca branca com operadora STFC (VulcaNet, TIP,
DiskFree) e tarifa "social" perto do atacado (R$ 0,03 a 0,06) exigem CNPJ e contrato; é uma
conversa para a ONG ter mais tarde, não resolve agora. Nenhum por minuto chega aos R$ 0,003 do
teto; só canal ilimitado ou retorno automático chegam.

### H. App próprio ou PWA

Decisão de 26/10 mantida: o difícil é tocar com o app fechado. PWA no iOS não toca com o app
fechado; no Android exige instalar e aceitar notificações. O WhatsApp (C) entrega exatamente o
que um app próprio entregaria, sem a manutenção, por isso substitui essa linha.

**Variante avaliada em 07/11/2026: app pronto de fabricante (Grandstream Wave + UCM RemoteConnect).**
O pai instala o Wave, lê um QR gerado pela central e vira ramal; a criança disca o ramal e a ligação
sai pela internet, sem operadora. Tecnicamente é simples e o toque no iPhone funciona por push.
Não entra como caminho principal por três motivos: (1) fere a meta 1, o pai precisa instalar app,
dar permissões e tirar da otimização de bateria (Android de Xiaomi/Samsung mata o app); (2) só
alcança quem instalou, então não serve para "discar o número de cada um" (avós, tios);
(3) exige PABX UCM (R$ 3 a 5 mil ou CloudUCM) e planos RemoteConnect por usuário remoto, e a nossa
central é Asterisk. O equivalente no Asterisk (softphone com push) é a própria linha H.
Pode voltar como **opcional** para famílias que queiram, cortando minutos do tronco Vono.

### I. Ideias menores que saíram da pesquisa

- **Validar o celular por "toque"** (flash call): ao cadastrar o número, a central dá um toque do
  número da rede e o pai digita os 4 últimos dígitos do número que apareceu, ou simplesmente a
  chamada perdida já confirma que o número existe. Grátis; substitui SMS de confirmação.
- **Até 5 celulares por criança.** 9+ID e 8+ID continuam para os dois primeiros (mãe e pai).
  Todos os cinco vão para teclas rápidas do GRP2601 quando o B21 fechar. E a criança pode discar o
  número completo (DDD + 9 dígitos) terminando em `#`; o AGI só completa se o número estiver na
  lista autorizada da família. O `#` resolve a ambiguidade com os serviços `1x` no plano de
  discagem do aparelho. Avó e tio entram sem prefixo novo.
- **Irmãos:** a "linha compartilhada" da Tin Can é o mesmo que uma pendência que toca em dois
  telefones; cabe na decisão de 07/11 (um aparelho por criança) sem mudar nada.
- **Pai no exterior:** só o WhatsApp (C) resolve de graça.

## 4. Anatel, revenda e os R$ 5

- Lei Geral de Telecomunicações, art. 61: serviço de valor adicionado não é serviço de
  telecomunicações e seu provedor é **usuário** do serviço que o suporta. O Telefone Fixo compra
  canais de operadoras autorizadas (Nvoip, Vono) e os usa para as famílias cadastradas, em lista
  fechada, sem oferecer ao público nem cobrar por minuto. É a posição de usuário, não de
  prestadora. Confirmar com o advogado (doc 13, pendência já aberta).
- Cobrar das famílias por ligação, mesmo R$ 5 "pelo celular", aproxima de revenda de STFC, que
  exige outorga; e a Resolução 777/2025 diz que não serão expedidas novas autorizações de STFC.
  Logo o caminho de cobrar por uso está fechado por desenho. Se um dia houver dinheiro das
  famílias, é contribuição associativa da ONG, fixa, sem relação com minutos, como decidido em
  05/11 (doações voluntárias).
- Cláusulas da Vono: o risco é contratual, não regulatório. A pergunta por escrito (§5) resolve.
- Autenticação de chamadas obrigatória a partir de 2028 (art. 84 do RGST) vai reduzir o spoof de
  identificador na entrada, que hoje é o risco aberto do doc 14.
- WhatsApp: a Meta vira operadora de dados dos pais que optarem; entra nos termos e na página de
  privacidade quando a fase 3 chegar.

## 5. Plano de prova

**B29. Retorno automático na Nvoip (descartado em 07/11; fica registrado).**
1. Tabela `chamadas_pendentes`; dialplan 9+ID com Dial de 5 s sem atender (`Dial(...,5)` seguido
   de `Hangup` do canal de saída, criança segue em `MusicOnHold` com anúncio); `check_entrada.py`
   consulta pendência pelo número do chamador e faz `Bridge`; timeout de 90 s com áudio; pendência
   válida por 10 min.
2. Ligação real do Daniel: 9+ID → celular mostra perdida → retorno → conversa. Conferir em
   `call_logs` e no CDR da Nvoip que o toque custou R$ 0,00.
3. Medir: tempo entre o toque e o retorno, taxa de retorno em 90 s, o que o pai achou.
4. Texto na página Celulares e no e-mail de boas-vindas: "salve este número; quando seu filho
   ligar e você vir uma chamada perdida dele, é só retornar".

**B30. Vono, 1 canal (R$ 50, sem fidelidade). Primeira prova.**
1. E-mail antes de contratar, guardando a resposta: "Sou pessoa física e opero uma central
   Asterisk para uma rede de telefones fixos de crianças; cada família cadastra até 5 celulares e
   as crianças ligam só para esses números. Previsão de X canais e Y minutos por mês. (a) Esse uso
   cabe nas condições gerais? (b) Os 5.000 minutos da cláusula 20.7 são por canal? (c) O canal é
   bidirecional e receber é grátis? (d) O tronco inclui número ou o número é à parte, e quanto
   custa? (e) Posso portar um número da Nvoip? (f) Aceitam CPF?"
2. Segundo tronco no Asterisk, rota 9+ID preferindo Vono, Nvoip de reserva. Ligação real nos dois
   sentidos. Qualidade e CDR.
3. Dois meses de medição do piloto: minutos por criança, hora de pico, chamadas simultâneas.
   Dimensionar pela tabela de §1 e contratar a faixa (9 canais já caem para R$ 40).
4. `custos.py`: teto em minutos da rede (80% de 5.000 × canais) e por criança (300 min); acima,
   rota A em vez de recusa. Painel do operador em minutos por tronco.

**B31. WhatsApp (quando houver CNPJ ou 2.000 mensagens/mês).**
Portfólio Meta, Cloud API com o número fixo da rede (verificação por ligação), ativar chamadas,
SIP TLS + SRTP no Asterisk com Opus, template "ligar" aprovado, webhook de permissão, tela na aba
Celulares. Começar pelo caminho grátis (pai liga; botão "Ligar") e só depois a chamada iniciada
pela central.

**Orçamento.** Dos R$ 20 mil de montagem, esta frente quase não gasta: R$ 50 a 400 por mês de
canais durante a prova, R$ 3 a 5 mil de advogado (já previsto no doc 13), zero em hardware. O
resto fica livre para aparelhos subsidiados e para a ONG. Em regime, com mil crianças: R$ 39 do
número Nvoip + R$ 400 a 640 de canais Vono + R$ 0 a 200 de WhatsApp = **R$ 440 a 880 por mês**,
dentro do teto de R$ 1.000, pais sem pagar nada, 5 horas por criança possíveis (o excedente dos
canais vai pelo retorno automático, que não custa).

## 6. Fontes (vistas em 07/11/2026)

- Meta, Cloud API Calling: developers.facebook.com/documentation/business-messaging/whatsapp/calling
  (overview, pricing, user-call-permissions, call-settings, call-button-messages-deep-links,
  messaging-limits). Preço em reais: nicochat.com/en/blog/whatsapp-business-calling-cost;
  twilio.com/en-us/whatsapp/pricing. Integração SIP com Asterisk: nimblea.pe/blog/whatsapp-business-calling-with-sip;
  orencloud.com/integrating-whatsapp-cloud-api-calling-into-asterisk-freepbx; community.asterisk.org (tópico 109945).
  Verificação de empresa no Brasil (CNPJ, CCMEI): maxbot.com.br, socialhub.pro, bossbot.uk/blog/setup-guide-br.
- Vono: falevono.com.br/servicos/sip-trunk (tabela por canal), condições gerais (cláusulas 20.2,
  20.5, 20.6, 20.7, lidas em 05/11).
- Nvoip: nvoip.com.br/en/virtual-number (recebimento grátis, 5 simultâneas, pacotes de 5 canais);
  nvoip.com.br/blog/ligacoes-ilimitadas (1 chamada simultânea por pacote); nvoip.com.br/blog/franquias-de-voz.
- Outros troncos: vozio.com.br/sip-trunk; avoip.com.br; vivo.com.br/para-empresas (SIP trunking);
  twsolutions.com.br; virtual-call.com/br.
- Operadoras fixas: planos.minhaconexao.com.br/claro/claro-fixo; melhorplano.net/telefone-fixo;
  vivo.com.br (nova condição comercial FWT); claro.com.br (sumário plano 115, 2024; plano 801
  Controle Flex, 2025); tim.com.br (regulamento TIM Controle Ligações Ilimitadas 2.0);
  investidura.com.br (MPF/ES x Claro).
- Gateways e chips: lojamundi.com.br/gateway-celular/gsm; khomp.com (KVoLTE); voipon.co.uk (Dinstar
  UC2000-VG-32T); tim.com.br/sobre-a-tim/institucional/seguranca/sms-pirata-spam; dgsolutions.com.br/chipeira-operadoras;
  tecnoblog.net (desligamento 2G/3G, VoLTE obrigatório na homologação).
- Interconexão: telesintese.com.br/anatel-reajusta-tarifas-de-chamadas-fixo-movel (VU-M 2023);
  teleco.com.br/tarifacel4.asp.
- Zadarma: zadarma.com/en/tariffs/numbers/brazil/mobile, zadarma.com/en/tariffs/calls/corporation/brazil.
- Anatel e LGT: Resolução 777/2025 (RGST); migalhas.com.br/depeso/16467 (VoIP e SVA);
  sippulse.com/en/blog/resolucao-777-e-o-novo-marco-do-stfc.
- Concorrentes: tincan.kids; techcrunch.com (Pinwheel Home, 14/07/2026); pinwheel.com/pinwheel-home-vs-tincan;
  investors.ooma.com (MyPhone); ringringclub.com/tincan-alternative; pausegadget.com/landline-for-kids;
  thenewhomephone.com/best-tin-can-alternatives-2026.
- Planos de celular com ilimitado: melhorplano.net/claro/planos-claro/prezao-claro; minhaconexao.com.br/planos/planos-de-celular.
- MEI 2026: opovo.com.br (DAS R$ 81,05 + ICMS/ISS).
