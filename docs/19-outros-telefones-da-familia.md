# 19. Outros telefones cadastrados pela família: proposta

Escrito em 12/11/2026 a partir do áudio da uma mãe do piloto (Maria) (mãe de uma menina do piloto, piloto; telefones emprestados
pelo Daniel) e do pedido do Daniel: "pense em uma solução para cadastrar vários outros telefones".
Reabre o item 22 do doc 08, descartado em 10/11, com a resposta ao problema que o derrubou (um número
cadastrado por duas famílias).

## 0. Resposta curta

- A Maria gostou do telefone (rápido de montar, sem operadora, as meninas usam o dia inteiro) e mesmo
  assim vai ficar com o fixo da Vivo. Dois motivos técnicos e um social: (1) o celular dela mostrou ora
  um número, ora outro, e o celular dela só toca para número salvo, então ligações de casa não tocaram;
  (2) o telefone só liga para a rede, e ela quer que as meninas liguem para parentes, para amigos fora
  da rede e para lugares ("liga na loja, pergunta se tem; liga no restaurante, pergunta se fecham"):
  contato com o mundo, aprender a dizer bom dia a um estranho; (3) a classe da a filha dela inteira começou a
  comprar fixo. O preço empatou: o fixo dela sai por R$ 5 por mês no contrato da Vivo.
- Proposta: a página Celulares vira **Telefones da família**. Além dos dois celulares com atalho (9+ID
  e 8+ID, como hoje), a família cadastra **até 20 outros números** do Brasil, fixo ou celular, cada um
  com um nome ("Vó Lúcia", "Casa do Théo", "Padaria"). A criança liga **discando o número completo com
  DDD e #**, como num telefone comum. Para cada número a família marca se ele **também pode ligar para a
  criança**; quando pode, toca no telefone dela com o nome no visor. Nada mais muda para quem não
  cadastrar.
- O que derrubou o item 22 (um fixo cadastrado por duas famílias: toca em quem?) se resolve com um menu
  de voz curto pelo nome, com a voz Piper que o portal já usa nos grupos: "Para a a filha dela, 1. Para o
  Pedro, 2." Número cadastrado por uma família só toca direto, como hoje.
- Custo por minuto: zero, pelos canais ilimitados da Vono (fixo e celular de todo o Brasil). O que
  cresce é minutagem e, com ela, canais; cabe nas metas do doc 17 (seção 3.4).
- Ligar para **qualquer** número (o "Party Line" da Tin Can, o que a Maria mais quer) é um interruptor
  a mais em cima do mesmo mecanismo. Está descrito na seção 4 como opção da família, desligada por
  padrão; recomendo decidir depois de medir o cadastro de números.
- Os dois números que ela viu são o da Nvoip (até 09/11 e na queda) e o da Vono (desde 09/11). A
  portabilidade marcada para 23/11 deixa um só. Até lá, a página já pede para salvar os dois.
- Esforço: um dia de código e testes, mais a prova B31 com ligação real. A Maria se ofereceu para
  continuar testando; é a família certa para provar vó e padaria.

## 1. O que a Maria disse

Áudio de 12/11/2026 às 21:26 (transcrição automática, revisada). Em resumo:

- A favor: "solução muito rápida: compra o telefone, clica duas coisas e a coisa acontece"; preguiça
  de lidar com operadora; textos e raciocínio bem explicados; "a coisa de ser em rede". "Foi uma
  revolução; se não tivesse tido esse eu não teria comprado fixo." A filha dela usa "direto, direto" com os
  telefones de duas amigas, que estão na casa dela.
- Contra: preço igual ao fixo da Vivo (R$ 5 por mês no contrato dela, aparelho comprado à parte); o
  telefone da rede "não tem só um número", quando liga para os dois celulares cadastrados "às vezes
  diz que é de um número, às vezes de outro", e o celular dela só toca de número conhecido, então as
  meninas ligaram e não tocou; "o que mais me pegou foi ele só ligar para a rede conhecida": as
  meninas têm parentes e amigos fora, e ela quer que liguem para lugares, "tem uma coisa de contato com
  o mundo que eu tenho achado muito importante, essas crianças aprenderem a falar oi, bom dia, tudo
  bem, tem alguém que pode me responder tal coisa"; e "na classe da filha dela começou esse movimento de
  comprar fixo", todo mundo ao mesmo tempo.
- Segue com os telefones e se oferece para continuar usando e dando retorno.

É o mesmo ponto da Rita (doc 18): o fixo comum alcança qualquer número. A diferença é que a Maria não
rejeitou a rede fechada como controle; rejeitou o alcance. E ela aponta um defeito concreto nosso (os
dois números) que o doc 18 não tinha.

## 2. O que existe hoje

- `familia_telefones`: até dois celulares por família (`MAX_POR_FAMILIA = 2`), posição 1 e 2, só
  celular brasileiro (`normalizar` recusa 11 dígitos sem o 9; 10 dígitos passa, mas o texto do site diz
  "só celular"). A criança disca 9+ID ou 8+ID; `chamadas.decidir_familia` acha o número pela posição e
  devolve o Dial; o dialplan prefere a Vono (`GROUP_COUNT(vono) < VONO_CANAIS`) e cai para a Nvoip.
- Entrada: `familia_telefones.decidir_entrada` acha **uma** família pelo número do chamador
  (`familia_por_numero`) e toca em todas as crianças dela com telefone conectado e dentro do horário.
  Número desconhecido ouve "número inválido".
- Plano de numeração (`ids.py`): 1XX serviços, [2-7]XXXXX ID, 0[1-9] grupo, 9/8+ID celulares. Não há
  prefixo de um dígito livre; por isso o B23 parou em dois celulares.
- Aparelho: o GRP260x sai com o dial plan padrão `{x+|\+x+|*x+|*xx*x+}` (P290, referência
  `grp260x_config_1.0.7.74.txt`), que aceita qualquer quantidade de dígitos e disca no # ou 4 s depois
  da última tecla (P85). Não precisa reprovisionar nada para discar 11 dígitos.
- Custo: Vono ilimitado para fixo e celular do Brasil, 4 canais, 5.000 min por canal por mês; tetos por
  criança em minutos (300 de saída, 1.800 de entrada) em `custos.py`; Nvoip por minuto como reserva.
- Voz: `voz.py` gera com Piper os apelidos das crianças e frases fixas para a chamada em grupo.

## 3. Proposta

### 3.1 Cadastro

Na mesma tabela `familia_telefones`, sem posição: `posicao` fica NULL para os "outros telefones";
coluna nova `recebe BOOLEAN NOT NULL DEFAULT TRUE` (pode ligar para a criança). Limites:
`MAX_POR_FAMILIA = 2` continua para os atalhos e `MAX_OUTROS = 20` para o resto (configurável; a
Pinwheel limita a 5 e a Tin Can não limita).

`normalizar` passa a aceitar fixo (10 dígitos, número começando de 2 a 5) e celular (11
dígitos com 9), sempre com DDD, só Brasil. Recusa prefixos de serviço e tarifados: 0300, 0500, 0800,
0900, 4003 e 4004 não são "telefone de alguém" e ficam fora. O texto do campo muda de "só celular"
para "telefone fixo ou celular do Brasil, com DDD".

Os números são da família, como hoje, e valem para todas as crianças dela.

### 3.2 Como a criança disca

O número completo com DDD, e # no fim: `11 3456 7890 #` ou `11 98765 4321 #`. Motivos:

- É o que a Maria pediu: um telefone que funciona como telefone. A criança aprende o número da avó.
- Não há prefixo de um dígito livre e um código de dois dígitos por contato ("*3#") é mais uma coisa
  para explicar (o doc 18 registrou que "9 e o ID, tudo junto, 7 dígitos" já travou a Rita).
- Não colide com nada: ID tem 6 dígitos, atalho 7, grupo 2, serviço 3; os padrões novos têm 10 ou 11
  dígitos, com 0 na frente opcional (11 ou 12). O dialplan casa padrão por tamanho.
- O aparelho já aceita (seção 2). Falta só provar no GRP real que 11 dígitos e # chegam inteiros à
  central (B31).

Os atalhos 9+ID e 8+ID continuam para os dois celulares de casa, que são os mais usados e os que a
criança menor precisa discar sem pensar. Mais tarde, se o B21 (teclas rápidas) fechar, "Vó" pode
virar tecla; e o GRP tem agenda remota por XML (P330/P331 na referência de P-values), que mostraria os
nomes no visor. Fica como B32, depois de provado o básico.

### 3.3 Entrada: quando um número cadastrado liga para a rede

`familia_por_numero` vira `familias_por_numero`, só com `recebe = TRUE`:

- **Uma família**: igual a hoje. Toca nas crianças dela com telefone conectado e dentro do horário,
  com o nome cadastrado no visor.
- **Mais de uma família** (a avó com netos em duas casas; a casa de um amigo cadastrada por três
  famílias): a central atende e diz, com os apelidos já gerados pelo Piper, "Para a a filha dela, 1. Para o
  Pedro, 2." (`Read()` de um dígito, duas tentativas, depois "não deu certo" e desliga). Até 9
  crianças; dentro de cada família continua tocando em todas as crianças daquela família. Isso tira do
  item 22 o motivo do descarte sem criar número novo (R$ 32,90 por mês cada) nem pedir o ID à avó.
- `recebe = FALSE` (padaria, restaurante): o número não toca; ouve "número inválido" como qualquer
  desconhecido. É o que mantém a promessa "só toca para quem você conhece".

Padrão da caixa "também pode ligar para a criança": marcada. Quem digitou o número é o responsável; o
caso comum é parente. Para lugares ele desmarca.

### 3.4 Limites e custo

- Saída e entrada contam nos mesmos tetos por criança (`custos._saida` passa a reconhecer destino de
  10 ou 11 dígitos). Com avó e amigos, 300 minutos de saída por mês (10 por dia) devem apertar antes
  dos 1.800 de entrada. Sugestão: subir para 600 quando a Vono tiver 8 canais; é uma variável de
  ambiente (`REDE_TETO_CRIANCA_MES`).
- Vono: o uso continua sendo "casa de família ligando para fixos e celulares do Brasil", sem
  discador, que foi o que o gerente de contas aprovou em áudio (B30). Não há tarifa por destino. O que
  muda é minutagem: o doc 17 dimensionou 10 canais para 30 min por criança e 16 para 60 min, com mil
  crianças; os 4 canais de hoje aguentam o piloto. Observar na aba Uso e em `GROUP_COUNT` quando
  começar a cair para a Nvoip.
- Para as famílias nada muda: cadastram e pronto, em minutos, nunca em reais (regra de 05/11: os pais veem minutos, não dinheiro).

### 3.5 Segurança

- Só número cadastrado completa. Trote em estranho não existe; o pior caso é trote na avó.
- Padrões de tamanho fixo no dialplan: "9090 + número" (a cobrar) tem 15 dígitos e não casa com
  nada; 00 e + (internacional) idem; 1XX continua serviço.
- O spoof do número do chamador (risco aberto no doc 14) ganha um pouco de superfície: mais números
  cadastrados, mais números que fazem tocar. Mitigação igual à de hoje (só toca, não dá acesso a
  nada) e a opção `recebe = FALSE`.
- `call_logs` passa a guardar o número externo discado (hoje já guarda o do chamador na entrada);
  a retenção existente cobre.

### 3.6 Site e cartão

- Aba "Celulares" vira **"Telefones"**. Três blocos, na ordem: "Celulares de casa" (os dois atalhos,
  como hoje), "Outros telefones" (lista: nome, número, se recebe, remover) e "Quem pode ligar para
  [criança]" (texto curto: os números acima marcados, mais o aviso do número da rede para salvar).
  Ação "Adicionar" no cabeçalho do bloco, formulário em página própria
  (`/crianca/<id>/telefones/novo`), sem details fechado (regra de hierarquia de páginas do site).
- Cartão impresso: continua com amigos e os dois atalhos. Página nova "Lista de telefones", em letra
  grande, para ficar ao lado do aparelho: nome e número completo de cada contato.
- Perguntas da capa: "Dá para ligar para celular ou telefone comum?" passa a "Para os telefones que
  a família cadastrar: celulares de casa, avós, amigos, a padaria. A criança disca o número com DDD.
  Nenhum outro número completa, nem para fora nem para dentro."

### 3.7 Legal

Já guardamos número e apelido de terceiros (os celulares da família). A linha da política de
privacidade ("Dos celulares da família: número e apelido...") vira "Dos telefones que a família
cadastra (celulares de casa, parentes, amigos, lugares): número e nome. Para a criança ligar para
eles e, quando a família marcar, para reconhecer quando eles ligam." O terceiro não é avisado; a
base é o interesse legítimo de quem cadastra, como em qualquer agenda. Entra na revisão do advogado
(doc 08, item 13), junto com o menu de voz que fala apelidos de crianças a quem liga: só fala
para números cadastrados com `recebe`, nunca para desconhecido.

## 4. Opção além: saída aberta ("liga na padaria sem cadastrar")

O que a Maria mais quer é a criança ligar para um lugar qualquer, na hora, sem o pai cadastrar antes.
É o Party Line da Tin Can (85% dos clientes pagam) e o Pinwheel "ilimitado". Em cima da seção 3 é um
interruptor por família: `familias.saida_aberta` (padrão falso). Com ele ligado,
`decidir_externo` deixa passar qualquer número de 10 ou 11 dígitos que `normalizar` aceite, mesmo
fora da lista; a entrada continua só da lista (é isso que segura telemarketing e estranho). Custo
igual (Vono). Texto: "Deixar [criança] ligar para qualquer telefone do Brasil. Ela continua recebendo
só de quem está na lista."

Contra: muda a promessa do site ("nem ela para fora"), abre trote em estranho, e é a família que
escolhe, não a rede. A favor: é a única resposta ao "contato com o mundo" dela e resolve a
comparação com o fixo comum pelo alcance, não só por custo e estranhos (doc 18, 4.2). Recomendação:
não agora. Primeiro medir, por um mês, quantos números as famílias cadastram e quantas pedem "qualquer
número"; o interruptor é uma tarde de trabalho quando (se) for a hora. Decisão do Daniel.

## 5. O que muda no código (estimativa: um dia)

| Onde | Mudança |
|---|---|
| `db.py`, `deploy/codigo.sh` | coluna `familia_telefones.recebe` (default true) |
| `ids.classificar_discado` | tipo novo `('externo', numero_normalizado)` para 10/11 dígitos, com 0 opcional |
| `familia_telefones.py` | `normalizar` aceita fixo e recusa 0300/0500/0800/0900/400X; `MAX_OUTROS`; `adicionar(..., recebe, posicao=None)`; `numero_cadastrado(conn, familia_id, numero)`; `familias_por_numero`; `decidir_entrada` devolve `ambiguo` com as opções |
| `chamadas.py` | `decidir_externo`: criança ativa, número na lista da família, horário da criança, teto; devolve o mesmo formato de `decidir_familia` (`dial;limite;vono`) |
| `custos.py` | `_saida` reconhece destino externo; `gasto_crianca_mes` e `uso_crianca_mes` somam as novas linhas |
| `extensions.conf` | padrões `_[1-9]XXXXXXXXX`, `_[1-9]XXXXXXXXXX`, `_0[1-9]XXXXXXXXX`, `_0[1-9]XXXXXXXXXX` → mesmo bloco de saída dos 9/8+ID (virar Gosub para não duplicar a rota Vono/Nvoip); em `[tronco-entrada]`, ramo `AMBIGUO`: `Read` + `Playback` dos apelidos e Dial no escolhido |
| `check_entrada.py` | passa a lista de opções (`ENTRADA_OPCOES`) ao dialplan |
| `voz.py` | frases "Para", "tecle" (ou gerar uma frase por opção: "Para a a filha dela, tecle 1") |
| `familia.py`, templates | aba Telefones, página de adicionar, lista impressa; `meus-dados.json` inclui `recebe` |
| `textos/privacidade.md`, landing | textos da seção 3.6 e 3.7 (termos e privacidade só depois do sim do Daniel) |
| testes | `test_familia_telefones` (normalizar, limites, ambiguidade), `test_chamadas` (externo permitido, fora da lista, teto), `test_fluxo_familia` (página) |

Deploy pela regra atual: `deploy/codigo.sh` (coluna e portal), `deploy/tronco-vono.sh` (dialplan,
sem reiniciar). Nada de pacote novo.

## 6. Prova (bancada B31)

Mudança em AGI e dialplan só vale depois de ligação real conferida em `call_logs`
(regra do projeto desde o B23). Roteiro, com o GRP de teste do Daniel e uma família real
depois (a Maria se ofereceu):

1. Cadastrar um fixo real e um celular de terceiro, um com `recebe`, outro sem.
2. Do GRP, discar os 11 dígitos e #: conferir que o aparelho manda o número inteiro (o `x+` do P290
   e o P85 de 4 s), que a central roteia pela Vono (`tronco = 'vono'` no log) e que há áudio nos dois
   sentidos. Repetir com 10 dígitos e com 0 na frente.
3. Discar um número de 11 dígitos não cadastrado: "esse número não está na sua lista" (ou a frase que
   couber; hoje seria `nao-esta-na-lista`).
4. Do número com `recebe`, ligar para o número da rede: toca com o nome no visor. Do número sem
   `recebe`: "número inválido".
5. Cadastrar o mesmo número em duas famílias (a do jose e a de teste): ligar dele e ouvir o menu pelos
   nomes; teclar cada opção; não teclar nada.
6. Conferir na aba Uso que os minutos entraram no teto da criança e no total da Vono.

## 7. Os dois números no celular dela

Causa provável: até 09/11 a saída era pela Nvoip, (11) 5108-3530; desde 09/11 sai pela Vono, (11)
5444-1774, com queda para a Nvoip quando a Vono recusa ou os canais estão cheios. Quem salvou o
primeiro número e recebeu ligação depois da troca viu "outro número". A página Celulares já mostra os
dois desde 09/11, mas a Maria cadastrou antes.

O que fazer: (a) a portabilidade do (11) 5108-3530 para a Vono em 23/11 (lembrete já agendado no
servidor) deixa um número só e encerra o assunto; (b) até lá, mandar um e-mail curto às famílias com
celular cadastrado: "quando [criança] liga, pode aparecer (11) 5444-1774 ou (11) 5108-3530; salve os
dois como Telefone Fixo"; (c) se o Daniel quiser confirmar que foi isso e não outra coisa, dá para
olhar `call_logs.tronco` das ligações das meninas (sem expor dados aqui).

## 8. Decisões para o Daniel

1. Seguir com a seção 3 (reabrir o item 22 do doc 08 nesses termos)?
2. Limite de 20 outros números por família está bom?
3. Caixa "também pode ligar para a criança" marcada por padrão?
4. Saída aberta (seção 4): não agora, medir primeiro?
5. Subir o teto de saída para 600 minutos junto com mais canais na Vono?
6. E-mail às famílias sobre os dois números antes da portabilidade?
7. Chamar a Maria para a prova B31 com a avó e um lugar de verdade?
