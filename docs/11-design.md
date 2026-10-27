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
