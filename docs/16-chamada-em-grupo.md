# 16 — Chamada em grupo: pesquisa e proposta (28/10/2026)

Pergunta do Daniel: o "0 na frente do número" é herança do projeto antigo. É uma boa ideia? Como uma
criança cria uma chamada em grupo de um jeito intuitivo, num telefone sem tela? A ideia bruta: uma aba
em que os pais montam o grupo, o site gera um número que toca para todos ao mesmo tempo, e quem atende
ouve que é uma chamada coletiva, para ninguém achar que está falando sozinho.

Regra fixa, dada por ele: só participa quem já é amigo de todos os outros (autorização mútua em todos
os pares). Nada aqui relaxa isso.

## 1. O que existe hoje (herdado do v1)

- A criança disca `0` + ID de um amigo. Isso abre uma "sala" (ConfBridge) com os dois.
- Qualquer outra criança que, naquele momento, ligue normalmente para um dos dois é **puxada para a
  sala**, se for amiga de todos. Ouve "entrando, N pessoas" e um bipe. Limite de 5.
- Não há nome de grupo, nem lista fixa de membros, nem anúncio de quem entrou ou saiu (só bipe), nem
  nada no site: o grupo nasce e morre dentro da chamada.

Problemas, com os olhos de uma criança de 6 a 10 anos e de um pai:

1. **"0 antes" é uma regra invisível.** Não tem como descobrir no aparelho; precisa estar escrito no
   cartão e lembrado. O cartão hoje diz "disque 0 antes do número", e isso só serve para abrir a sala
   com UMA pessoa. Os outros têm de ser convocados por fora (gritar pela janela, ligar antes).
2. **O terceiro entra por acidente.** A criança C liga para B querendo uma conversa a dois e cai numa
   sala com A sem ter pedido. É surpresa para C e para quem já estava. Para a família de C, é uma
   chamada que ela não autorizou daquele jeito: autorizou B, não "B e quem estiver com B".
3. **Ninguém chama ninguém.** Não existe "ligar para todos de uma vez". A dor que o Daniel descreveu
   (achar que está falando sozinho) nasce daí: a sala pode ficar com uma pessoa esperando sem saber
   se alguém vem.
4. **Sem identificação.** O visor do GRP2601 mostra o apelido de quem ligou; numa sala, o segundo a
   entrar não sabe quem mais está lá, e o bipe não diz quem entrou ou saiu.

Conclusão: a mecânica do `0` não é boa para a rede nova. O conceito de "chamada em grupo" vale a pena
(doc 08 item 5: "as crianças gostam"), mas precisa de grupo com nome, membros fixos, chamada que toca
para todos, e voz que diga o que está acontecendo.

## 2. O que a pesquisa diz

### 2.1 Produtos para crianças

- **Tin Can** (EUA, a referência de "telefone fixo para criança") **não tem** chamada em grupo nem a
  três; está no roteiro, segundo o FAQ. O plano "Party Line" é só o nome do plano pago para ligar para
  números comuns. Ou seja: é um recurso que diferencia.
- **Kite Phone** (Reino Unido) faz conferência de até 5: a criança liga para um amigo, "adiciona"
  outro, e vira grupo. Dado útil do teste deles em Londres (nov/2025): as chamadas das crianças tiveram
  em média 3 a 4 participantes. O modelo "adicionar durante a chamada" depende de tela e de botão
  "adicionar"; num GRP2601 seria o flash/transfer de telefone fixo, que a própria literatura de
  telefonia descreve como o ponto em que os adultos erram (tempo do flash curto demais ou longo demais
  derruba a ligação; fica pior a cada participante). Não serve para criança sem tela.
- **Messenger Kids** (Meta): grupos só existem quando um adulto aprovado os cria; os pais são
  avisados de cada contato novo e podem gerenciar; a criança pode sair do grupo quando quiser. É o
  padrão de mercado para "grupo de criança": adulto cria, família vê, criança sai sozinha.
- **Alexa Group Drop In**: "chamar todos os aparelhos de uma vez", cada um atende individualmente,
  todos entram na mesma conversa. É a mecânica mais próxima da ideia do Daniel: um comando, toca em
  todos, cada um entra quando atende. Problema relatado: dois aparelhos na mesma sala dão microfonia.
  No nosso caso são casas diferentes, não se aplica.
- **Relay** (walkie-talkie infantil): "canais" fixos de grupo com um botão. Mostra que, para criança,
  o grupo tem de ser uma coisa pré-montada e com nome, não uma operação durante a chamada.

### 2.2 Conferência em áudio: tons, anúncios e silêncio

- Fornecedores corporativos (Teams, Skype for Business, Pexip) desligam por padrão tons e anúncios de
  entrada e saída, porque em reuniões grandes atrapalham. Mas o mesmo material diz que **quem entra
  só por áudio fica confuso com o silêncio** e pede uma confirmação ("você entrou na chamada"), e que
  **anúncio de nome faz sentido em reuniões pequenas** ou sensíveis. Grupo de 3 ou 4 crianças, sem
  tela: é exatamente o caso em que nome falado é a decisão certa, e silêncio é o erro.
- AT&T e CallBridge dão ao anfitrião a escolha entre tom, silêncio e nome; um pedido de patente do
  Google propõe um tom distinto por participante justamente porque "sem isso ninguém sabe quem
  entrou ou saiu". Para criança, nome falado é mais claro que tom por pessoa.
- Pesquisa de earcons (Brewster, Glasgow): sons estruturados funcionam melhor que bipes soltos; timbres
  musicais melhor que ondas simples; ritmos bem diferentes para eventos diferentes; e som serve
  especialmente para **informação escondida** (estado, confirmação) que não aparece em tela. Nosso
  telefone é só áudio: estado da chamada (tocando, entrou, saiu, sozinho) tem de virar som ou fala.

### 2.3 Voz para crianças

- Soapbox Labs (voz para crianças): perguntas "um nível só" (nunca dependem de memória), no máximo
  três opções, comandos universais sempre disponíveis, uma só estrutura de frase no produto inteiro.
- Testes da BBC com crianças: a pergunta tem de ser o fim da frase, e o sistema tem de estar ouvindo
  imediatamente; crianças respondem antes de o áudio acabar.
- Nielsen Norman (3 a 12 anos): instruções claras e específicas, feedback imediato, aproveitar
  convenções que a criança já conhece. A convenção aqui é "telefone": tira do gancho, disca, toca,
  atende. Tudo que fugir disso precisa de voz explicando.
- Turn-taking: conversa com várias pessoas é mais difícil para criança do que a dois (revisões de
  desenvolvimento e um estudo de 2026 na ACL mostram pausas e sobreposições diferentes das de adultos).
  Grupos de fonoaudiologia e de habilidades sociais para 6 a 10 anos trabalham com 3 a 5 crianças;
  um estudo de 2024 (ASHA) achou associação negativa entre grupos de 5 a 10 e resultados de linguagem.
  Isso, somado à média de 3 a 4 da Kite, sustenta **limite de 4 na chamada** (3 amigos + quem ligou),
  com 5 como teto técnico.

### 2.4 O que o Asterisk já oferece (ConfBridge)

Tudo abaixo existe pronto, só configurar: `sound_join` / `sound_leave` (bipes), `sound_has_joined` /
`sound_has_left` (anúncio "fulano entrou/saiu"), `sound_only_person` ("você é o único na chamada"),
`announce_user_count` (quantos estão), `announce_join_leave` (gravar o nome ao entrar, descartado: pedir
para a criança gravar o nome é um passo a mais e falha com criança pequena; usamos o apelido já
conhecido), menu por tecla (`participant_count` em `*` para ouvir quantos estão, `leave_conference`).
Para "tocar para todos ao mesmo tempo", a aplicação `Originate` do dialplan com a opção `a` (assíncrona)
chama cada membro em paralelo e o coloca na sala quando atende; é o padrão usado pela comunidade.

## 3. Proposta

### 3.1 Conceito em uma frase

**O grupo é uma coisa com nome que os pais montam no site, aparece no cartão com um número curto, e a
criança liga para ele como liga para um amigo.** Toca em todas as casas ao mesmo tempo; quem atende ouve
que é uma chamada em grupo e quem já está nela; todos ouvem quem entra e quem sai.

### 3.2 Como a criança usa (o lado do aparelho)

Discar: **`0` e um dígito**, por exemplo `01#` para o primeiro grupo da criança, `02#` para o segundo.
Fica no cartão ao lado do telefone, na mesma tabela dos amigos:

```
Amigo                 Discar
Beto                  329674#
Alice                 731006#
Turma do futebol      01#       (grupo: Beto, Alice, Theo)
```

Por que assim, e não as alternativas:

| Opção | Problema |
| --- | --- |
| `0` + ID do amigo (hoje) | não é "ligar para o grupo", é "ligar para um e torcer"; terceiro entra por acidente |
| ID de 6 dígitos para o grupo, igual para todos | consistente com o modelo de ID, mas 6 dígitos a mais para decorar, e o cartão de cada criança já tem os amigos com 6 |
| tecla do aparelho | melhor opção para criança pequena, mas o GRP2601 tem 1 tecla livre (VPK 2) e a B21 ainda não confirmou que a tecla chega pelo GDMS; fica como camada por cima, não como único caminho |
| `0` + 1 dígito, por criança | 2 dígitos, nunca conflita com ID (que começa em 2 a 7) nem com `100`, cabe no cartão, até 9 grupos por criança, resolvido pelo próprio ID de quem liga |

O número é **por criança**: Beto disca `01#` para o mesmo grupo que José chama com `02#`, porque cada
cartão lista os grupos daquela criança na ordem dela. A criança nunca precisa saber o número do outro.
Quando a B21 confirmar as teclas, a VPK 2 do aparelho vira "Grupo 1" (um toque, sem discar nada).

**Sequência de áudio, passo a passo** (frases curtas, uma ideia por frase, sem pergunta, como manda a
pesquisa de voz para crianças; vozes geradas com Piper pt-BR, offline, uma vez por frase e uma por
apelido):

1. José tira do gancho e disca `01#`.
2. Ouve: *"Chamada em grupo: Turma do futebol. Chamando Beto, Alice e Theo."* Depois, tom de chamando
   (ringback) enquanto os aparelhos tocam. Nada de silêncio.
3. Nas casas de Beto, Alice e Theo o telefone toca; o visor mostra **"Grupo: Turma do futebol (José)"**.
   Quem olha o visor já sabe que é grupo e quem chamou.
4. Alice atende e ouve: *"Chamada em grupo de José: Turma do futebol. Na chamada: José."* e um tom
   curto de entrada. José ouve o tom e *"Alice entrou."* Os dois já conversam.
5. Beto atende: ouve *"Chamada em grupo de José: Turma do futebol. Na chamada: José e Alice."* Todos
   ouvem *"Beto entrou."*
6. Theo não atende em 40 segundos: todos ouvem *"Theo não atendeu."* (uma vez). Se Theo estiver fora do
   horário dele ou silenciado, nem toca, e no início José ouve *"Theo não pode agora."* no lugar do nome.
7. Se ninguém atender: *"Ninguém atendeu. Tente de novo mais tarde."* e desliga.
8. Durante a chamada, `*` lê *"Na chamada: José, Alice e você."* (uma tecla só, sempre a mesma).
9. Alice desliga: todos ouvem o tom de saída e *"Alice saiu."* Se sobrar um: *"Você é o único na
   chamada."* e, 30 segundos depois sem ninguém, desliga com *"A chamada em grupo terminou."*
10. Theo, que perdeu a chamada, disca `01#` dele dez minutos depois: se a chamada ainda estiver
    acontecendo, entra nela (*"Entrando na chamada em grupo. Na chamada: José e Beto."*); se não, começa
    uma nova. A mesma ação ("ligar para o grupo") sempre faz a coisa certa.

Quem ligou não é "dono" da chamada: se José desligar, os outros continuam. É o comportamento esperado
de um telefone (e o contrário surpreende criança).

Limites: 4 na chamada (3 membros + quem ligou) por padrão. O grupo tem o mesmo tamanho, 4 crianças contando
quem criou, para todo o grupo sempre caber na chamada (decisão do Daniel em 28/10; a versão anterior permitia
8 no grupo, e "até 7" num formulário contra "até 4" no outro confundia). *"A chamada está cheia"* só acontece
numa entrada tardia por acaso de corrida. Turma maior vira dois grupos.

### 3.3 Como a família monta (o lado do site)

Onde: **dentro da aba Amigos**, abaixo da lista de amigos, uma seção **"Grupos para ligar juntos"**.
Não uma aba nova: as abas já são cinco no celular, e grupo é feito de amigos. (A aba "Turmas" continua
sendo o diretório da escola; é outra coisa. Para não confundir, na tela de turma entra um atalho "Criar
grupo de ligação com a turma", que pré-seleciona os amigos aceitos daquela turma.)

Criar: nome (até 20 caracteres, porque vai para o visor do aparelho e para a voz) + caixas de seleção
com os **amigos aceitos** da criança. Nada mais. O site mostra o número que a criança vai discar
(`01#`) e manda reimprimir o cartão.

Regra "todos amigos entre si", sem vazar informação sobre terceiros:

- Na criação, o site **não diz** quem é amigo de quem entre os outros (a família de José não tem o
  direito de saber se Beto e Alice são amigos). Diz só, se for o caso: *"Nem todos deste grupo se
  conhecem na rede. O grupo chama só quem é amigo de todos; as outras famílias veem o que falta."*
- Na casa de cada membro, a seção mostra **"Grupos em que Beto está"** com o grupo criado pela família
  de José e, se faltar algo, a informação que é dela: *"Para Beto participar, falta aceitar amizade com
  Alice."* Isso é dado da própria família (as amizades do próprio filho), não de terceiros.
- Cada família pode tirar o próprio filho do grupo com um botão **"Sair do grupo"**, sem aviso ao
  criador além de o nome sumir da lista. Remover ou bloquear uma amizade tira a criança de todos os
  grupos com aquele amigo, na hora.

Nenhum consentimento novo: a base legal é a mesma da amizade (autorização mútua por par, já aceita
pelos responsáveis). O grupo só combina autorizações que já existem. Vale registrar na política de
privacidade uma linha: "grupos de ligação reúnem só amigos já autorizados; qualquer família tira o filho
quando quiser".

Horários e "silenciar agora" valem por membro: quem está fora do horário não toca e é anunciado como
"não pode agora". Quem liga fora do próprio horário ouve a mesma mensagem de sempre.

Histórico: a chamada aparece como *"Grupo: Turma do futebol"* com o tempo de cada participante (o
registro por participante já existe em `conf_leave.py`; ganha o nome do grupo).

Celulares dos pais não entram em grupo nesta fase (custo por minuto e complexidade de tronco). Fica
anotado para depois.

### 3.4 Design do som e da voz

- Uma só voz (Piper pt-BR, voz neutra), velocidade um pouco abaixo do normal, frases de até 8 palavras.
- Apelidos lidos como texto; dígitos no apelido viram números falados ("jose sete"). O site já pede
  apelido sem acento; a tela de apelido ganha a dica "é assim que o telefone vai falar o nome".
- Três sons curtos e diferentes (ritmo e timbre distintos, como manda a pesquisa de earcons): entrou
  (duas notas subindo), saiu (duas notas descendo), chamada cheia ou erro (uma nota grave). Nada de
  bipe genérico igual para tudo, que é o que existe hoje.
- Nunca silêncio por mais de 3 segundos sem um motivo audível: tom de chamando enquanto toca, "você é
  o único" quando ficar só.
- Sem perguntas. A única interação por tecla é `*` para ouvir quem está. Desligar é colocar no gancho.

### 3.5 O que sai

- `_0[2-7]XXXXX` (o `0` + ID) e a regra "ligação normal cai na sala se o destino estiver numa sala".
  As duas trocam previsibilidade por surpresa. O cartão perde a frase do "0 antes" e ganha a linha
  dos grupos.

## 4. Implementação (resumo para dimensionar)

| Peça | O que | Esforço |
| --- | --- | --- |
| Banco | `grupos` (id, crianca_dona_id, nome, criado_em, ativo) e `grupo_membros` (grupo_id, crianca_id, codigo 1..9 por criança, entrou_em, saiu_em) | 0,5 dia |
| Serviço | `grupos.py`: criar, listar por criança, sair, remover; `decidir_grupo(conn, caller, codigo, agora)` devolve sala, nome, membros chamáveis agora (amigos de todos os que vão participar, dentro do horário, não silenciados) e os motivos dos que ficam fora | 1 dia |
| Site | seção na aba Amigos (criar, listar, sair), atalho na turma, linha no cartão, aviso no histórico, dica na tela de apelido | 1 dia |
| Áudio | Piper pt-BR no servidor; frases fixas geradas no deploy; áudio do apelido gerado ao criar a criança (e ao mudar o apelido); guardado em `/usr/share/asterisk/sounds/apelidos/<id>.wav` | 0,5 dia |
| Asterisk | `_0X` → AGI `check_grupo.py` → anúncio → `Originate(PJSIP/<id>,exten,grupo-entrar,<sala>,,a)` para cada membro com `CALLERID(name)="Grupo: <nome> (<apelido>)"` → `ConfBridge` com perfil `grupo_bridge` (`sound_has_joined`/`has_left` com o apelido, `sound_only_person`, `max_members`) e menu `*`; contexto `grupo-entrar` toca o anúncio e entra; registro por participante reaproveita `conf_leave.py` | 1,5 dia |
| Bancada | B25: dois GRP2601 + um softphone fazendo o terceiro; conferir visor, anúncios, "não atendeu", entrada tardia, horário por membro, histórico | 0,5 dia |

Total na casa de 5 dias de trabalho. Risco técnico principal: o `Originate` assíncrono e o registro de
tempo por participante; ambos têm referência na comunidade e o v1 já tinha a parte do registro.

## 5. Decisões (28/10/2026)

1. Conceito: grupo com nome montado pelos pais, toca em todos, **numeração por criança** (`0` + dígito,
   `01#`, `02#` no cartão de cada uma). Confirmado ("esse modelo parece ótimo").
2. Limite na chamada: **4** (3 membros + quem ligou). Confirmado.
3. A chamada **continua até todos desligarem**; quem ligou não manda nela. Confirmado.
4. O `0` + ID continua **só no projeto antigo** (`telefone_fixo` v1, instância separada). Na rede nova
   sai, junto com a regra de "cair na sala" ao ligar para alguém que está numa sala. Confirmado.
5. Nome da seção: "Grupos para ligar juntos" (aplicado; fácil de trocar).

## 6. Implementação (28/10/2026)

Feita conforme a secao 3, com uma diferenca tecnica em relacao a tabela da secao 4: em vez de `Originate` +
`ConfBridge` no dialplan, a chamada e controlada por um **servico Python ligado ao ARI** (a interface REST e
de eventos do Asterisk 20): e o unico jeito limpo de tocar frases para todos ("Beto entrou", "Theo nao
atendeu", "Voce e o unico"), de saber quem nao atendeu e de registrar o tempo de cada participante.

- `rede/db.py`: tabelas `grupos` e `grupo_membros` (codigo 1..9 por crianca, unico entre os grupos ativos dela).
- `rede/servicos/grupos.py`: criar (so amigos aceitos da dona, nome de 2 a 20), listar por crianca (o que
  falta e dado so da propria crianca), sair, remover (so a dona), `decidir` (clique em ordem de entrada no
  grupo + horario e silenciar por membro), `pode_entrar` (entrada tardia), `registrar_chamada` (uma linha
  por participante em `call_logs`, callee `GRUPO`, tempo em comum com cada um dos outros).
- `rede/voz.py`: frases fixas, tons (entrou, saiu, erro) e tom de chamando gerados por sox; apelidos e nomes
  de grupo falados por piper (pt-BR, offline) ou espeak-ng; gravados em `/var/lib/rede-aberta/sons`
  (link `rede/` nos sons do Asterisk). Gerados ao criar a crianca e o grupo; nunca derrubam a operacao.
- `rede/grupo/`: `ari.py` (cliente REST minimo), `app.py` (a chamada dirigida por eventos; testavel com
  um ARI falso), `servico.py` (processo `rede-grupo`, websocket de eventos, reconexao).
- Dialplan: `_0[1-9]` -> `Stasis(grupo,chamador,<codigo>)`; se o servico estiver fora, "nao deu certo".
  O `0` + ID e a regra de "cair na sala" sairam, junto com `check_group.py`, `conf_leave.py` e o confbridge.
- Site: secao "Grupos para ligar juntos" na aba Amigos (criar, listar, sair, remover), atalho na turma
  (pre-seleciona os amigos aceitos da turma), linha no cartao impresso, dica na tela de apelido.
- Instalacao: `deploy/grupos.sh` (tabelas, websockets e piper no venv, sons, ARI/HTTP em localhost com
  senha gerada no servidor, musica de espera, dialplan, servico systemd, reinicios).
- Testes: `tests/test_grupos.py` (servico e site) e `tests/test_grupo_ari.py` (fluxo completo, ninguem
  atendeu, quem ligou desistiu, entrada tardia e limite, bloqueios, sem audio de apelido).
- Bancada: B25 feita com dois aparelhos em 28/10 (`bancada/B25-chamada-em-grupo.md`): chamada, anúncios, grupo
  inexistente, ninguém atendeu e histórico confirmados. A parte de três participantes espera um softphone.
- Instalado no servidor em 28/10/2026: serviços `asterisk`, `rede-grupo` e `rede-portal` ativos, app `grupo` registrada no ARI, piper
  com a voz `pt_BR-faber-medium`, 19 frases, 4 tons e os apelidos das crianças cadastradas. Teste de fumaça por ARI (chamada local
  para `01` com um número inexistente) percorreu Stasis, serviço, decisão, frase e registro em `call_logs` sem tocar aparelho.
  Tropeços: a primeira versão de `gerar_tons` travou o sox e gravou um wav de 40 GB que encheu o disco (apagado, tons refeitos,
  rotação de log adicionada; doc 14 item 8).

Amizade removida ou bloqueada depois de o grupo existir: ninguem e tirado do grupo automaticamente; a
regra do clique ja impede os dois de caírem na mesma chamada, e a pagina de cada familia mostra o que falta.

## 7. Fontes

- Tin Can sem grupo (FAQ, "três vias no roteiro"; "Party Line" é plano): https://tincan.kids/products/tin-can ;
  https://screenwiseapp.com/guides/tin-can-for-kids ; https://phone.kitestudios.org/guides/tin-can-uk-alternative
- Kite Phone, conferência até 5 e média de 3 a 4 no teste de Londres: https://phone.kitestudios.org/guides/tin-can-uk-alternative ; https://phone.kitestudios.org/safety
- Messenger Kids, grupos criados por adulto aprovado, pais avisados, criança sai: https://www.bark.us/guides/app-management/messenger-kids ; https://www.weareteachers.com/messenger-kids-connect-classmates/
- Alexa Group Drop In (toca em todos, cada um atende): https://www.slashgear.com/1783213/alexa-drop-in-feature-explained-how-works-different-than-announcements ; https://www.gearbrain.com/amp/alexa-drop-in-all-devices-2646147119
- Relay, canais de grupo com um botão: https://safewise.com/resources/republic-wireless-relay-review ; https://www.androidcentral.com/republic-relay-review
- Tons e anúncios em conferência (padrões, confusão com silêncio, nome em reunião pequena): https://learn.microsoft.com/en-us/skypeforbusiness/manage/conferencing/join-and-leave-announcements ; https://docs.pexip.com/admin/joining_leaving_tones.htm ; https://community.cisco.com/t5/collaboration-applications/telepresence-conductor-no-confirmation-tone-for-audio/m-p/3438868 ; https://www.its.ms.gov/sites/default/files/ServicesPDFs/ATT%20Reservationless%20Touch%20Tone%20Commands.pdf ; https://patents.google.com/patent/US9300807
- Três vias por flash e seus problemas: https://community.cisco.com/t5/atas-gateways-and-accessories/call-waiting-and-3-way-calling/m-p/4045393 ; https://sandman.com/knowledgebase/conference-call-troubleshooting
- Earcons (Brewster, Glasgow): https://www.dcs.gla.ac.uk/~stephen/papers/CHI93.PDF ; https://www.dcs.gla.ac.uk/~stephen/earcon_guidelines.shtml
- Voz para crianças: https://soapboxlabs.com/blog/6-ways-to-design-voice-experiences-for-kids ; https://www.nngroup.com/videos/designing-children/
- Turn-taking infantil em grupo: https://pmc.ncbi.nlm.nih.gov/articles/PMC12627207/ ; https://aclanthology.org/2026.iwsds-1.34/ ; https://dl.acm.org/doi/10.1145/2522848.2522871
- Tamanho de grupo (fonoaudiologia, 6 a 10 anos): https://pubs.asha.org/doi/10.1044/2024_LSHSS-23-00047 ; https://csd.uiowa.edu/node/886 ; https://sltforkids.co.uk/speech-clinic/services/groups/in-schools/social-communication-group/
- ConfBridge (opções de som e anúncio, menu): https://docs.asterisk.org/Configuration/Applications/Conferencing-Applications/ConfBridge/ConfBridge-Configuration/
- Originate assíncrono para vários participantes: https://lists.digium.com/pipermail/asterisk-users/2021-September/296060.html ; https://community.asterisk.org/t/how-to-invite-user-together-to-confbridge/46536
- Teclas VPK do GRP260x (discagem rápida): https://documentation.grandstream.com/knowledge-base/grp26xx-vpk-virtual-multi-purpose-keys-guide/
