# 11 — Design do site (23/10/2026)

Direção: **sério, mas não chato**. O site fala com o responsável (quem cria a conta), mas tem de
parecer o tipo de coisa que uma criança de 8 a 13 anos acharia legal ter em casa: um objeto, não um
aplicativo.

## Referências lidas

- **Tin Can** (tincan.kids): tom nostálgico e bem-humorado ("Brand new old phone", "All talk, no
  smarts"), cores quentes (dourado, aquamarine), copy curta, três promessas ("No apps, no texts /
  No stranger danger / No surprises"), depoimentos de pais, preço claro. Aproveitamos a estrutura
  (herói, três promessas, como funciona, para quem é, FAQ) e o humor contido; não o visual.
- **Pinwheel** (pinwheel.com): fala com os pais em tom de confiança ("Tech you can trust"), fotos
  de família, muitas seções de controle parental. Aproveitamos a ideia de dizer explicitamente o
  que o responsável vê e o que a criança vê.
- Guias de design para faixa etária: 8–13 anos responde mal a brilho e mascote ("menos blinky
  things"), bem a espaço, tipografia forte e um ponto de cor; evitar "excesso de gentileza".

## Decisões

- **Paleta**: papel quente (`#faf6ee`), tinta (`#1b2432`), coral do fio (`#e8542c`) como única cor
  de ação, azul-mar (`#1f7a8c`) para links e secundário, amarelo-sol só em marcadores e etiquetas.
- **Tipografia**: Fraunces (títulos, serifa com personalidade), Nunito (texto), JetBrains Mono
  (IDs e MACs). Google Fonts.
- **Marca**: selo coral com um monofone + "Rede Aberta" em Fraunces; subtítulo "telefone para
  ligar para os amigos". Favicon em SVG inline.
- **Objeto, não app**: ilustração em SVG de um telefone de mesa com fio enrolado e o ID
  `34 56 78` embaixo; o ID da criança aparece numa "etiqueta" tracejada amarela, como a etiqueta
  do aparelho.
- **Cadastro em 5 passos visíveis**: Conta → E-mail → Aceite → Criança → Telefone. A conta pede
  o nome do responsável; o apelido da criança vem no passo 4, depois do aceite (LGPD art. 14).
  De propósito não pedimos o nome completo nem a data de nascimento da criança; o site diz isso.
- **Reenvio do código** na tela de confirmação (limite de 3 por hora, código anterior invalidado).
- **Página inicial pública** em `/` para quem não está logado: herói, três promessas, como funciona,
  para quem é, "feito para durar, não para vender", FAQ. Logado, `/` continua indo para a criança.
- Bootstrap 5 continua por baixo (grade, formulários, alertas); o visual vem de `style.css`.

## Fora do escopo por enquanto

Fotos reais (precisam de autorização de imagem), depoimentos, nome definitivo e domínio da ONG,
página "Sobre" com a organização, versão em inglês.

## Revisão de 26/10/2026 (tarde)

Depois de usar o site com os dois aparelhos, o Daniel pediu: tirar a ilustração do telefone (feia e com
números que não significam nada), tirar "Para crianças de 8 a 13 anos" (público-alvo, não limite),
evitar travessões e outros tiques de texto gerado, e abandonar a combinação serifa + papel creme,
que ficou com cara de "site de vibe coding".

Decisões:
- **Uma só família tipográfica, Atkinson Hyperlegible**, do Braille Institute, desenhada para leitura
  fácil: distingue 0/O, 1/l/I (zero cortado). Importa num site onde a família digita S/N, MAC e IDs.
  Sem fonte de título, sem fonte mono: códigos usam a mesma fonte com algarismos tabulares.
- **Fundo branco**, texto quase preto (#1f2328), superfícies cinza-claro, bordas neutras. O coral
  continua como única cor de ação, um pouco mais escuro (#d9480f) para contraste no branco.
- Hero só com texto e dois botões. Nada de ilustração até termos fotografia real.
- Sem travessões em títulos, e-mails e textos. Títulos de página usam "Página | Rede Aberta".
  Assuntos de e-mail em frase ("Seu código de verificação na Rede Aberta").
- Sem faixa etária no site. A pesquisa de referência (8 a 13) fica só neste documento.

## Auditoria do celular (27/10/2026, a partir do vídeo)

Capturas de todas as 21 telas do fluxo em 390 px (`docs/midia/gravar-video.py` tem o roteiro; o de
auditoria está no scratchpad da sessão). Problemas encontrados e corrigidos no mesmo dia:

- Cabeçalho quebrava em duas linhas (marca e três botões): agora uma linha, botões menores.
- Abas só com ícone no celular: agora ícone em cima e nome embaixo (Amigos, Turmas, Horários, Ligações, Telefone).
- Passo ativo da linha do tempo ficava estreito (coluna do marcador + duas molduras aninhadas): no celular o
  cartão do passo usa a largura toda e o marcador fica dentro dele; o bloco "Onde vai cada cabo" perdeu a
  moldura interna. O desenho foi redesenhado maior (portas e numeração ~1,6x).
- Página inicial estourava 12 px na horizontal (`row g-5`): `g-4 gx-lg-5`.
- Cartão para imprimir sem `viewport`: abria em 980 px no celular.
- Pedidos de amizade: texto e botões disputavam a mesma linha e a mensagem quebrava palavra por palavra:
  agora empilhados no celular.
- Textos encurtados: resumo da página do telefone, descrições dos modelos.

Regra que fica: toda tela nova passa pela captura em 390 px antes de ir para o ar.

## Identidade visual (28/10/2026)

O Daniel trouxe um pacote de identidade (`telefone-fixo-identidade.zip`: manual da marca, logos em SVG,
favicon, fontes, tokens, componentes e a página inicial aplicada em 1280 e 390 px). A ideia: o disco do
telefone e a linguagem gráfica das estatais de telecomunicação dos anos 1970 a 1990 (Telebrás, orelhão,
lista telefônica, formulário de repartição), relida com WCAG 2.2 AA, alvos de 44 px e foco visível.
"Parece um serviço público que funciona." O site inteiro foi refeito só na estética; nenhum texto mudou.

O que entrou:
- **Faixa**: cabeçalho azul-estatal (#1D4F91) com fio laranja (#E8761E) de 4 px embaixo; rodapé em
  azul-profundo com o fio em cima. Símbolo negativo (disco branco) a 44 px e o nome em letreiro
  (Archivo 800, largura 125 %, caixa alta). No celular o nome quebra em duas linhas; com a conta aberta
  (três botões) fica só o símbolo.
- **Tipografia**: Archivo (variável, eixos de peso e largura) e IBM Plex Mono 500 para ID, S/N, MAC,
  horários e números do cartão. Corpo de 18 px (17 no celular). Fontes hospedadas em
  `static/fontes/` como woff2 (subconjunto latino, 117 KB + 18 KB); o Google Fonts saiu do site e da CSP.
- **Forma**: cantos de 4 px em tudo, fios de 1 e 2 px em vez de sombras, círculo só para o que é furo
  do disco (número de passo, ponto de estado do aviso, marcador da linha do tempo). Botões com 48 px
  (44 nos pequenos), anel de foco laranja-texto de 3 px.
- **Componentes aplicados**: Passo (furo azul com algarismo mono) em "Como funciona" e na lista dos
  cabos; Princípio (fio azul em cima, sem ícone) nos três "só"; Aviso (bloco cinza com ponto colorido)
  nos alertas; Campo (rótulo em caixa alta espaçada, borda de 2 px); IdCrianca (`_id.html`: seis casas
  com fio azul embaixo, agrupadas 2+2+2 como no resto do site e nos cartões já impressos; o manual
  sugere 3+3, mantivemos a convenção existente); Cartão (`cartao.html`: faixa azul, lista zebrada,
  números em mono, legível em preto e branco); Faixa no cabeçalho e rodapé.
- **Página inicial** conforme a aplicação do pacote: rótulo, pergunta como título, "Você precisa… de um
  telefone fixo" com marca-texto amarelo (uma vez por tela), botões Começar e Como funciona, o cartão
  impresso ilustrado ao lado (nomes fictícios), três princípios em cinza, "Como funciona" com letreiro
  à esquerda e cinco furos à direita, faixa azul-profunda com rótulo amarelo e link "Ver o código"
  (repositório público), perguntas com letreiro à esquerda.
- **Favicon e prévia**: `static/marca/` (favicon.svg, .ico, apple-touch-icon) e `static/og.png` do pacote.
- O desenho dos cabos e dos modelos trocou o coral antigo pelo laranja-orelhão e o azul-mar pelo
  azul-estatal; o gráfico do histórico ficou azul; os chips de dia da semana deixaram de ser pílulas.

Fora por enquanto: tema escuro (o manual traz os tokens; Bootstrap tem muitas utilidades de cor nos
templates e isso pede uma passada própria) e ícones Lucide (seguem os Bootstrap Icons, de traço parecido).

Auditoria: 25 telas em 390 e 1280 px (script `auditar2.py` no scratchpad da sessão, derivado do roteiro
do vídeo). Corrigido no mesmo dia: nome da marca invadia os botões no celular; letreiro "Perguntas comuns"
a 48 px invadia a coluna ao lado (agora até 36 px); linha do celular cadastrado quebrava no meio do número;
hover preso do mouse do Playwright fazia um botão de contorno parecer preenchido (artefato de captura, não
do site: o script agora afasta o mouse antes de cada captura). Sem estouro horizontal em nenhuma tela.

## Revisão de 28/10/2026 (tarde): identidade desfeita

O Daniel olhou o site com a identidade aplicada e não gostou: "essa tentativa de estatal não funcionou".
Uma segunda rodada (disco grande, carimbo, fio espiral, fichas, páginas amarelas) pareceu "muito poluída e
confusa"; uma terceira, só com contornos escuros nos botões, agradou nos botões mas não salvou o conjunto.
Decisão: voltar ao design de 27/10 à noite (Atkinson Hyperlegible, fundo branco, coral como única ação),
exatamente como estava depois das correções de texto da Carol. O pacote de identidade fica guardado em
`~/Desktop/telefone-fixo-identidade.zip` e a seção acima registra o que foi tentado. Lição registrada:
aplicar identidade não pode mexer em texto nem na ordem dos blocos, e mudança de visual inteira merece uma
prova numa página só antes de ir para o site todo.

## Aba Amigos (28/10/2026, noite): hierarquia em três blocos

Problema relatado pelo Daniel: "Grupos para ligar juntos" não era encontrado sem Ctrl+F; a aba parecia três coisas (pedir amizade, amigos, grupos) sem separação nem hierarquia. Na captura de antes, o formulário de pedir amizade ocupava a primeira tela inteira no celular, cinco títulos iguais (h5) se seguiam, cada contato era um cartão com dois botões, e tanto "Criar um grupo" quanto "Bloqueados" estavam em `<details>` fechados.

O que a pesquisa diz, e o que foi aplicado:

- Conteúdo escondido em acordeão/`details` é perdido; só esconder o que é secundário e dar sinal claro de abrir (NN/g, "Accordions on Desktop"; GOV.UK Design System, "Accordion": "não use para conteúdo que todos precisam ver; teste primeiro sem"). Aplicado: "Criar grupo" e "Adicionar amigo" viraram botões no cabeçalho de cada bloco, com página própria para o formulário. Só "Bloqueados" ficou em `details`, porque é raro.
- Hierarquia visual: no máximo três tamanhos, dois elementos grandes, contêineres com parcimônia; o mais importante vem primeiro e os títulos começam pela palavra que informa (NN/g, "Visual Hierarchy" e "F-Shaped Pattern"). Aplicado: dois títulos grandes com linha grossa embaixo (Amigos, Grupos para ligar juntos), subtítulos pequenos (Aguardando, Bloqueados), listas com linhas em vez de um cartão por contato, ações de remover/bloquear como links discretos à direita.
- O que exige resposta vem antes do resto: pedidos recebidos num bloco amarelo no topo, com o número no título ("1 pedido de amizade para você responder").
- Formulário em página própria (padrão "uma coisa por página" do GOV.UK): a página da lista é só leitura e decisão; `contatos/pedir` e `grupos/novo` são os formulários, e o erro de validação volta para o formulário com o que foi digitado. Sem amigos ainda, o formulário de pedir aparece aberto na própria aba, porque é a única coisa a fazer.
- Prova em tela antes de subir: capturas em 390 e 1280 (`~/Desktop/aba-amigos-antes-depois/`). Deploy de rotina com o novo `deploy/codigo.sh` (só código, reinicia o portal).

Fontes: nngroup.com/articles/accordions-on-desktop, nngroup.com/articles/visual-hierarchy-ux-definition, nngroup.com/articles/f-shaped-pattern-reading-web-content, nngroup.com/articles/tabs-used-right, design-system.service.gov.uk/components/accordion, design-system.service.gov.uk/components/summary-list.

## ID da criança no alto de todas as páginas, com botão Copiar (05/11/2026)

Problema relatado pelo Daniel depois de testar com outra família: ao abrir a conta para passar o ID, levou alguns segundos para achá-lo, e não havia como copiar. Na captura de antes, a aba Amigos (onde a conta abre) só mostrava o ID em letra miúda embaixo do logo, e no celular nem isso, porque essa linha some abaixo de 480 px. A etiqueta amarela só existia na aba Telefone e na lista de crianças.

O que mudou:

- Faixa com a etiqueta amarela "ID de <apelido>" acima das abas, em todas as páginas da criança (`base.html`, mesma condição das abas). Um lugar só, sempre o mesmo: quem aprende onde está não procura de novo. Fica acima das abas porque as abas são seções da criança; as abas continuam fixas ao rolar e a faixa rola com a página.
- Botão "Copiar" dentro da etiqueta, com texto e ícone (ícone sozinho não se explica). Copia os 6 números sem espaço. Confirma no próprio botão ("Copiado", verde, 2,5 s) e anuncia para leitor de tela (`#copiado-aviso`, `aria-live`). Sem a API de área de transferência, tenta o método antigo; se nem esse der, deixa o número selecionado.
- A mesma etiqueta com Copiar (`_etiqueta.html`) vale para a lista de crianças e para o código da turma, que também é um número para passar adiante.
- O que saiu, por estar duplicado: a etiqueta dentro da aba Telefone e a linha "APELIDO · ID" embaixo do logo (o cabeçalho volta a mostrar a frase do projeto em todas as páginas).
- Colar: o campo "ID do amigo" aceita a mensagem inteira colada ("o ID é 12 34 56") e fica só com o número. No celular o WhatsApp copia a mensagem toda, não um trecho.
- De passagem: o número da etiqueta não quebra mais em duas linhas com apelido comprido (lista de crianças no celular).

Prova em tela: capturas em 390 e 1280 (`~/Desktop/id-copiar-antes-depois/`), com o clique no botão conferido contra a área de transferência do navegador. Testes em `tests/test_id_visivel.py`.

## Celulares vira aba da criança; cabeçalho só com Sair (05/11/2026)

Pedido do Daniel: Celulares deve ser uma aba como Amigos, Turmas e Horários, e com isso os botões "Crianças" e "Celulares" do cabeçalho deixam de ser necessários.

- Aba "Celulares" entre Ligações e Telefone, em `/crianca/<id>/celulares`. Os números continuam sendo da família (valem para todas as crianças dela); a aba aparece em cada criança. O endereço antigo `/celulares` redireciona para a aba da primeira criança.
- A aba fala só em minutos (quanto a criança usou e quanto ainda pode ligar no mês). Dinheiro aparece apenas no painel do operador.
- Cabeçalho da família: selo, nome e "Sair" (o operador tem também "Painel"). Com menos botões, nada passa da largura em 320, 360 e 390 px.
- Trocar de criança: em família com mais de uma, a faixa do ID mostra "Trocar de criança", que leva à lista. A lista também fica no rodapé ("Crianças"), em `/criancas`, e é onde se adiciona outra criança. O selo continua levando à página inicial.
- Seis abas cabem no celular (ícone em cima, nome embaixo), conferido em 360 px.

## Página técnica "Como funciona por dentro" e link do código (05/11/2026)

Pedido do Daniel: o site dizia "código aberto" sem link para o código, e faltava um lugar para quem quer
entender onde fica cada dado e como o telefone se registra.

- **Link do código** (`cfg.CODIGO_URL`, variável `REDE_CODIGO_URL`): na página inicial, dentro do bloco
  "Sem fins lucrativos, com código aberto"; no rodapé de todas as páginas ("Código"); e na página técnica.
  O link no rodapé também atende à AGPL (oferecer o código a quem usa o serviço pela rede).
- **Seção no fim da página inicial**, depois das perguntas comuns: "Quer entender por dentro?", com botão
  para a página técnica e para o código. Nenhum texto existente da página inicial foi alterado.
- **Página `/por-dentro`** (`por_dentro.html`), pública, sete blocos numerados: as peças, como o telefone
  entra na rede, o que acontece numa ligação, celular da família, onde fica cada dado, segurança (o que tem
  e o que falta) e o código (arquivos por onde começar a ler, com link direto).
- **Quatro desenhos em SVG** no próprio HTML, com as cores da identidade: laranja para telefonia, azul para
  site e configuração, tracejado para serviços de fora. O `viewBox` tem 360 de largura para a letra não ficar
  pequena no celular (cerca de 12 px em tela de 360); no computador o desenho fica ao lado do texto, com no
  máximo 460 px. A tabela de dados vira lista no celular.
- **Regra de manutenção**: tudo o que a página afirma foi conferido no código e no servidor em 05/11/2026
  (região, transportes SIP, modo "ponteiro" do GDMS, cópia diária, prazos de retenção). Mudou a central, o
  provisionamento ou a política de privacidade, a página tem de ser revista. Os prazos repetem a política de
  privacidade, que continua sendo o texto que vale; o do histórico vem de `RETENCAO_CHAMADAS_DIAS`.
- **O que a página admitia que faltava** (revisto pelo Daniel no mesmo dia): nada mais. A ligação passou a ser
  cifrada com TLS e SRTP em todas as linhas (doc 14, bancada B26) e o bloco virou só "Segurança", dizendo isso
  e avisando que o trecho da operadora, nas ligações com celular, segue como telefonia comum. A cópia de
  segurança fora do servidor foi feita e a frase saiu. A frase sobre auditoria externa saiu. A menção ao Google Fonts e ao jsDelivr saiu da página e foi para
  a política de privacidade 2026-11-a (doc 13), junto com as cópias de segurança.
- Página inicial, mesma data: a pergunta sobre celular e o bloco "Só quem a família aprovou" passam a citar
  os celulares da própria família, para não contradizer a aba Celulares.
- Testes em `tests/test_por_dentro.py` (inclui conferir que os arquivos citados existem no repositório).

## Aba Telefones (13/11/2026): celulares de casa e outros telefones

Doc 20, etapa C. A aba Celulares virou Telefones (ícone `bi-telephone-forward`, endereço antigo redireciona).
Mesma hierarquia da aba Amigos: blocos com cabeçalho de linha grossa, ação no cabeçalho, listas em linhas,
formulário em página própria.

- Ordem: aviso dos dois números (12/11) e fase de teste no topo; "Celulares de casa" (os dois atalhos 9/8+ID);
  "Outros telefones" (nome, número em cinza, "discar 3456 7890#" com dígitos agrupados, "liga para X" ou "só X
  liga", ações "Deixar/Não deixar ligar para cá" e "Remover"); "Como X disca" (DDD da casa com origem e botão
  Trocar/Confirmar/Escolher; duas frases de regra; link do cartão); "Quem liga para X" (quem recebe, com o
  número da rede na caixa grande).
- Página "Adicionar telefone": "Quem é" antes do número (decisão de 13/11); um campo de número só (padrão GOV.UK:
  aceita colado, com ou sem DDD); texto de ajuda diz qual DDD vale e de onde veio; caixa "também pode ligar para
  X" marcada por padrão. Erro volta com o que foi digitado. Confirmação diz o número entendido, o que a criança
  disca e o DDD da casa quando foi usado.
- Página "DDD da casa" (`/ddd`): molde da de fuso; sugestão com origem em uma frase; select dos 67 DDDs com a
  cidade de referência.
- Cartão: outros telefones entram na mesma tabela, com o que discar; dica do DDD no rodapé.
- Capturas em 390 e 1280 conferidas em 13/11 (telefones cheia e vazia, novo, novo-celular, ddd, cartão), sem
  estouro horizontal. O vídeo didático não passa por essa aba.

## Nome falado da criança (13/11/2026, fim do dia)

Pedido do Daniel depois do menu de entrada: além do apelido (único, é o que outras famílias veem), a família
pode dar um nome curto opcional ("Ana"). A voz usa o nome nos grupos e no menu ("para falar com Ana, tecle
1"); se duas opções do mesmo menu têm o mesmo nome, a voz volta ao apelido. A família vê "Ana (ana01)" na
faixa do ID e na lista de crianças; nas frases das abas continua o apelido. Campo no passo 4 do cadastro e na
página `/crianca/<id>/nome` (link na lista de crianças). Apelidos e nomes falados a 1,25 de ritmo.

