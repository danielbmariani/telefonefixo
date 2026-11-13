# 20. Telefones da família: pesquisa e plano de implementação

Escrito em 12/11/2026 (noite), a partir do pedido do Daniel depois do doc 19: a família cadastra um
número e a criança passa a poder ligar para ele; no cadastro há um DDD padrão da casa, estimado pelo
IP, para a família digitar só o número; a criança disca só o número quando é do mesmo DDD e DDD +
número quando é de fora (sem 0, sem código de operadora). Este doc responde se isso faz sentido,
reúne a pesquisa que sustenta cada escolha e detalha a implementação, com telas.

## 0. Resposta curta

- **Faz sentido, com um ajuste que o deixa mais robusto.** A central não precisa "adivinhar" o DDD na
  hora da ligação: ela procura o que a criança discou **na lista da família**, comparando o fim do
  número. Quem disca `3456 7890 #` liga para a Vó se a Vó está na lista com qualquer DDD; se houver
  duas entradas com o mesmo número local em DDDs diferentes (raro), vale o DDD da casa. Assim o DDD
  estimado pelo IP serve para o que ele é bom (facilitar o cadastro e imprimir a lista do jeito que a
  criança disca) e nunca faz uma ligação cair no lugar errado. Quando, e se, a "saída aberta" do doc 19
  entrar, o DDD da casa passa a ser decisivo, e a estrutura já estará pronta.
- **Como a criança disca.** Mesmo DDD: só o número (8 dígitos fixo, 9 celular). Outro DDD: DDD +
  número (10 ou 11 dígitos). Sempre com `#` no fim, como hoje. A central também aceita 0 na frente e
  55 na frente, porque alguém vai discar assim. Nada disso colide com IDs (6), atalhos 9/8+ID (7),
  grupos (2) e serviços (3): os tamanhos são todos diferentes.
- **DDD da casa.** Três fontes, nesta ordem: o que a família escolheu; o DDD dos celulares já
  cadastrados; a localização do IP de onde o telefone da criança busca a configuração (GeoLite2, que
  já roda no servidor para conferir o fuso) convertida em DDD pelo município mais próximo. Protótipo
  rodado no servidor em 12/11 acertou o DDD em 11 de 11 IPs de teste (seção 2.3). Sempre mostrado e
  trocável; nunca decidido em silêncio.
- **O aparelho não muda.** O GRP260x sai de fábrica com o dial plan `{x+|...}`: aceita qualquer
  quantidade de dígitos e envia no `#` ou 4 s depois da última tecla. Um dial plan restritivo não
  faria o telefone discar mais rápido (seção 2.4), então não vale o risco.
- **Entrada**: cada número tem a marca "também pode ligar para a criança" (padrão: sim). Número
  cadastrado por mais de uma família ouve o menu pelos nomes (doc 19, 3.3).
- **Tamanho**: quatro etapas, cerca de três dias de trabalho, cada uma com deploy e prova própria
  (seção 6). A primeira ligação real pela Vono para um fixo é a prova que destrava o resto (B31).

## 1. O pedido e a leitura dele

O que o Daniel pediu (12/11): (a) a pessoa cadastra o número e a criança pode ligar; (b) no cadastro,
um DDD padrão estimado pela geolocalização do IP, para digitar só o número, sem 55 nem 11; (c) a
criança disca só o número para o mesmo DDD e DDD + número para fora.

O que isso implica e não estava dito:

1. Há **dois DDDs padrão em jogo**, e são o mesmo: o do formulário (para a família) e o da discagem
   (para a criança). Os dois vêm do mesmo lugar, o "DDD da casa", guardado na família.
2. A regra (c) é a regra do celular, não a do fixo comum. No fixo comum se disca 0 + operadora + DDD;
   no celular se disca DDD + número. As crianças vão aprender a do celular, que é a que vão usar a vida
   toda. Fica registrado no site: "sem o 0, sem o código da operadora".
3. "A criança pode ligar para esse número" continua sendo lista fechada: só completa o que está
   cadastrado. A "saída aberta" segue como opção futura (doc 19, seção 4).
4. O DDD estimado pode errar (IP de 4G, CGNAT, família que mudou de cidade). Por isso a discagem não
   pode depender dele (seção 3.2) e a estimativa precisa ser visível e trocável (seção 4.4).

## 2. Pesquisa

### 2.1 Numeração brasileira (o que a central precisa saber)

Fontes: Anatel, Plano de Numeração Brasileiro e Resolução 749/2022 (Regulamento de Numeração);
Wikipédia "Números de telefone no Brasil" para as faixas; lista de DDDs conferida contra a base de
municípios (seção 2.2).

| Item | Regra | Consequência para nós |
|---|---|---|
| Código Nacional (DDD) | 67 códigos, dois dígitos, primeiro de 1 a 9 e segundo de 1 a 9 (nunca 0). SP: 11 a 19; RJ: 21, 22, 24; MG: 31 a 38; PR 41 a 46; SC 47 a 49 (42 compartilhado); RS 51 a 55; DF/GO 61; GO 62, 64; TO 63; MT 65, 66; MS 67; AC 68; RO 69; BA 71 a 77; SE 79; PE 81, 87; AL 82; PB 83; RN 84; CE 85, 88; PI 86, 89; PA 91 a 94; AM 92, 97; RR 95; AP 96; MA 98, 99 | validar DDD contra a lista dos 67; não aceitar "10", "20", "30"... |
| Fixo | 8 dígitos; prefixos 2000 a 3999, 4010 a 4999, 5000 a 5999 (5700 a 5799 rural). Primeiro dígito 2 a 5 | `[2-5]XXXXXXX`; **4000 a 4009 não é fixo de alguém** (serviços com tarifa local, como 4003 e 4004): recusar no cadastro |
| Celular | 9 dígitos, sempre começando por 9 (nono dígito concluído em 2016 em todo o país) | `9XXXXXXXX`; 8 dígitos começando por 9 não existe mais |
| Longa distância nacional | 0 + CSP (código da operadora, 2 dígitos) + DDD + número | a criança **não** disca assim; a central disca pela Vono como `0 + DDD + número` (B30), sem CSP |
| A cobrar | 9090 + número (local) e 90 + CSP + DDD + número | 4 dígitos antes do número: não casa com nenhum padrão nosso; bloqueado por construção |
| Internacional | 00 + CSP + país + número | fora: só Brasil (já é a regra dos celulares) |
| Não geográficos | 0800 (grátis), 0300 e 0303 (pagos; 0303 é telemarketing), 0500 (doação), 0900 (valor adicionado), 400X (tarifa local) | recusar no cadastro com mensagem própria: "esse é um número de serviço, não de pessoa" |
| Utilidade pública e emergência | 100 a 199 (Res. 358/2004: 100, 128 e 180 a 199 são emergência: 190 polícia, 192 SAMU, 193 bombeiros, 180 mulher, 181 denúncia, 100 direitos humanos, 188 CVV...). A página oficial da Anatel (gov.br/anatel, "SUP") estava atrás de um captcha em 12/11 | 1XX já é "serviço" no nosso plano (só 100 = hora certa funciona). Decisão de produto, fora deste doc: a rede **não** dá acesso a 190/192/193 hoje; a Tin Can libera 911 sempre. Registrar como item 26 do doc 08 para o Daniel decidir |

Conflitos de prefixo no nosso plano (tudo o que a criança pode discar):

| Dígitos | Padrão | O que é |
|---|---|---|
| 2 | `0[1-9]` | grupo |
| 3 | `1XX` | serviço |
| 6 | `[2-7]XXXXX` | ID de criança |
| 7 | `[89][2-7]XXXXX` | celular 1 e 2 de casa |
| 8 | `[2-5]XXXXXXX` | **novo**: fixo do DDD da casa |
| 9 | `9XXXXXXXX` | **novo**: celular do DDD da casa |
| 10 | `[1-9][1-9][2-5]XXXXXXX` | **novo**: DDD + fixo |
| 11 | `[1-9][1-9]9XXXXXXXX` | **novo**: DDD + celular |
| 11, 12 | `0` + os dois de cima | tolerância: alguém vai discar com 0 |
| 12, 13 | `55` + os dois de cima | tolerância: número colado do WhatsApp |

Nenhum padrão tem o mesmo tamanho que outro com o mesmo começo, então a central nunca fica em
dúvida sobre uma sequência completa. O único efeito colateral é de **prefixo**: um fixo local de 8
dígitos começa como um ID de 6 (`34567890` contém `345678`). Se a criança parar 4 s no sexto dígito, o
aparelho envia o ID, e a central responde "não está na lista de amigos" (ou toca em uma criança real,
com probabilidade de 1 em 600 mil por ID existente). Isso já acontece hoje com qualquer pausa longa
no meio de um número e a resposta é a mesma de sempre: ensinar o `#` (está no cartão) e não mexer no
tempo de 4 s, que uma criança precisa.

### 2.2 Base de municípios com DDD

`kelvins/municipios-brasileiros` (GitHub, licença MIT): CSV com 5.571 municípios, código IBGE, nome,
latitude, longitude, UF, DDD e fuso. Conferido em 12/11: 67 DDDs distintos, nenhum município sem
DDD, São Paulo 11, Guarulhos 11, Jundiaí 11, Campinas 19, Santos 13, Sorocaba 15. É compilação de
terceiros (já teve correção de códigos IBGE em issue antiga), então entra no repositório como arquivo
estático (`rede/dados/municipios.csv`, ~300 KB) com um teste que confere as 27 capitais e os 67
DDDs. A BrasilAPI (`/api/ddd/v1/<ddd>`, lista de cidades por DDD) serve de contraprova, mas não vira
dependência em tempo de execução: nada sai do servidor.

### 2.3 IP para DDD: GeoLite2 + município mais próximo

O que já existe: `rede/geoip.py` lê a base GeoLite2-City no próprio servidor (`deploy/geoip.sh`,
atualização semanal) e devolve o fuso do IP de onde o telefone buscou a configuração
(`telefones.ultimo_prov_ip`). O registro da MaxMind traz também cidade, UF, latitude, longitude e
raio de precisão em km.

Protótipo rodado no servidor em 12/11/2026 (`ddd_por_ip.py`: IP → lat/lon → município mais próximo
no CSV → DDD), com IPs públicos conhecidos:

| IP (dono) | GeoLite2 | Município mais próximo | DDD | Certo? |
|---|---|---|---|---|
| Registro.br, SP | São Paulo, raio 5 km | Diadema (6 km) | 11 | sim |
| UFMG | Belo Horizonte, 10 km | Belo Horizonte | 31 | sim |
| UFPE | Recife, 5 km | Olinda (2 km) | 81 | sim |
| UFRGS | Porto Alegre, 5 km | Porto Alegre | 51 | sim |
| USP São Carlos | São Carlos, 10 km | São Carlos | 16 | sim |
| UFSC | Florianópolis, 5 km | Florianópolis | 48 | sim |
| UnB | Brasília, 20 km | Brasília | 61 | sim |
| UFPA | Ananindeua, 10 km | Ananindeua | 91 | sim |
| UFAM | Manaus, 5 km | Manaus | 92 | sim |
| UFC | Fortaleza, 10 km | Fortaleza | 85 | sim |
| casa do Daniel (IP visto na bancada) | São Paulo, 20 km | São Paulo | 11 | sim |

Limites, pela própria MaxMind e pela literatura: a precisão é um raio, não uma cidade; IP de celular
(4G/5G) e CGNAT caem no gateway da operadora, muitas vezes a capital do estado; a documentação do
`geoip.py` já diz isso. Por isso:

- Usar o IP **do telefone da criança** (fibra ou cabo da casa), não o do navegador do responsável,
  que pode estar no 4G. O do navegador é o último recurso, quando o telefone ainda não buscou
  configuração.
- Casar primeiro por **nome da cidade + UF** (quando o GeoLite2 traz), depois por município mais
  próximo. O caso Registro.br → Diadema mostra o porquê: o ponto caiu a 6 km do centro, mas na mesma
  região de DDD; perto de uma divisa (11/19 em Jundiaí e Campinas, 11/15 em Sorocaba) o nome evita
  o erro.
- Raio acima de 50 km ou sem cidade: ainda sugerir, mas dizer "parece"; abaixo, dizer "o telefone
  está em Campinas (DDD 19)".
- O DDD dos **celulares já cadastrados** vem antes do IP: é o sinal mais forte que temos (a Maria tem
  dois celulares 11).

### 2.4 O aparelho: dial plan, tempo e tecla de envio

Referência local `bancada/referencia-pvalues/grp260x_config_1.0.7.74.txt` e o guia de administração
GRP260x: P290 (dial plan) sai `{x+|\+x+|*x+|*xx*x+}`, ou seja, qualquer sequência de dígitos; P85
("No Key Entry Timeout") 4 s; P72 ("Key as Send") = `#`. Um dial plan restritivo serviria só para
recusar números no aparelho; segundo quem já tentou com GXP (fórum 3CX), o Grandstream não disca na
hora quando a sequência casa com uma regra, continua esperando o tempo ou a tecla de envio. Logo não
há ganho em reprovisionar os aparelhos e há risco (um erro no P290 deixa a casa sem ligar). Decisão:
**não mexer no telefone**. O que muda é só na central.

Para depois (B32): o GRP tem agenda remota por XML (P330 = 3 para HTTPS, P331 caminho `host/path`,
P332 intervalo em minutos, P333 remove entradas manuais). Com ela, os nomes aparecem no visor e a
criança pode escolher "Vó" na lista do aparelho em vez de discar. Exige provar no aparelho e servir o
XML com token por telefone (como o `/p/<token>/cfg`).

### 2.5 Como pedir um telefone num formulário (GOV.UK Design System)

O padrão "Telephone numbers" do GOV.UK: **um campo só**, não separar DDD do número; deixar a pessoa
digitar no formato que conhece e aceitar espaços, hífens, parênteses e código de país; `type="tel"` e
`autocomplete="tel"`; não usar máscara; não reformatar o que a pessoa digitou enquanto ela digita; no
erro, dizer o formato com exemplo ("digite com DDD, como 11 3456 7890"). Nosso campo atual já faz
isso. O "DDD padrão" entra como **texto de ajuda e preenchimento do resultado**, não como campo
separado: "Sem DDD, vale o 11 (DDD da casa). Trocar."

### 2.6 Como os outros fazem

- Tin Can (Party Line): lista de contatos aprovados no app dos pais; números comuns só no plano pago;
  "phone book" de papel na caixa; a criança disca o número. O FCC classificou o serviço como de acesso
  restrito por causa da lista fechada. Sem detalhe público sobre discagem local.
- Pinwheel Home: 5 números aprovados no plano básico.
- Celulares: todos discam DDD + número sem 0; a maioria das pessoas nem lembra o CSP. Essa é a regra
  que a criança vai reconhecer depois.

## 3. Desenho da solução

### 3.1 Dados

```
familias
  + ddd TEXT            -- '11'; NULL = ainda não definido (usa a sugestão)
  + ddd_origem TEXT     -- 'familia' | 'celulares' | 'telefone_ip' | 'navegador_ip' | NULL

familia_telefones       (já existe)
  posicao INTEGER       -- 1, 2 = atalhos 9/8+ID; NULL = outros telefones
  + recebe BOOLEAN NOT NULL DEFAULT TRUE   -- pode ligar para as crianças da família
  numero TEXT           -- sempre DDD + número (10 ou 11 dígitos), como hoje
  apelido TEXT          -- 'Vó Lúcia', 'Casa do Théo', 'Padaria'

rede/dados/municipios.csv   -- 5.571 linhas, MIT; carregado em memória na primeira consulta
```

Limites: `MAX_POR_FAMILIA = 2` (atalhos) e `MAX_OUTROS = 20`, os dois em config (`REDE_MAX_OUTROS`;
0 desliga o bloco inteiro, que é a chave de lançamento).

### 3.2 Discagem: o que a central faz com o que a criança discou

`ids.classificar_discado` ganha dois tipos:

```
('externo_local', '34567890')        8 ou 9 dígitos
('externo', '1134567890')            10 ou 11, com 0 ou 55 na frente já retirados
```

`chamadas.decidir_externo(conn, caller, tipo, digitos)`:

1. Criança ativa (como nas outras rotas).
2. Lista da família: `familia_telefones` ativos da família da criança, **sem** restringir a `posicao`
   (os celulares de casa também podem ser discados pelo número completo; é natural a criança
   aprender o número da mãe).
3. Casamento:
   - `externo`: número igual.
   - `externo_local`: entradas cuja parte local (número sem DDD) é igual. Uma só → ela. Mais de uma →
     a do DDD da casa; sem DDD da casa ou nenhuma nele → bloqueio `EXTERNO_AMBIGUO` ("Esse número
     existe em dois DDDs na sua lista. Disque com o DDD").
   - Nenhuma → `EXTERNO_FORA_DA_LISTA` com som novo: "Esse telefone não está na lista de casa."
4. Horário da criança; teto de minutos (`custos.segundos_permitidos`, sentido saída); Vono disponível.
5. Devolve `PJSIP/<numero>@nvoip;limite=<s>;vono=<0|1>`, o mesmo formato de `decidir_familia`, e o
   dialplan reaproveita o bloco de saída (Vono com queda para Nvoip).

Tolerâncias deliberadas: `0` na frente (quem aprendeu no fixo), `55` na frente (número colado),
DDD da própria casa digitado (sempre vale). Recusas deliberadas: 4 dígitos antes do número (a
cobrar), `00` (internacional), 1XX além do 100 (serviço), tamanhos fora da tabela.

Por que casar pelo fim e não "DDD da casa + número": o DDD da casa pode estar errado ou vazio
(família nova, IP de 4G, mudança) e a lista é a verdade. Com lista fechada, casar pelo fim nunca liga
para o lugar errado: o pior caso é a ambiguidade acima, que pede o DDD.

### 3.3 Entrada

Como no doc 19, 3.3: `familias_por_numero(numero)` só com `recebe = TRUE`; uma família toca direto
com o apelido no visor; mais de uma ouve "Para a Ana, 1. Para o Pedro, 2." com os apelidos que o
Piper já gera; `recebe = FALSE` ouve "número inválido" como qualquer desconhecido.

### 3.4 DDD da casa: estimativa e ciclo de vida

```
ddd.sugerir(conn, familia_id, ip_navegador=None) -> (ddd, origem, descricao)
  1. familias.ddd definido                 -> ('11', 'familia', None)
  2. DDD mais frequente dos celulares      -> ('11', 'celulares', 'o DDD dos celulares de casa')
  3. telefones.ultimo_prov_ip de uma criança da família -> geoip -> ('19', 'telefone_ip', 'Campinas')
  4. ip_navegador -> geoip                 -> ('19', 'navegador_ip', 'Campinas')
  5. None                                  -> (None, None, None): formulário pede o DDD junto
```

`ddd.por_ip(ip, cfg)`: registro GeoLite2 → se país ≠ BR, None → casar cidade + UF no CSV → senão
município mais próximo por lat/lon → `(ddd, nome_municipio, raio_km)`. Só IPs públicos; sem base,
None; nunca levanta exceção (padrão do `geoip.py`).

Quando vira definitivo: no primeiro "Adicionar telefone" salvo sem DDD explícito, ou quando a
família confirma na página "DDD da casa". Guardado com `ddd_origem` e auditoria. A sugestão
nunca é gravada em silêncio no cadastro da conta: a família ainda não tem telefone nem celular nessa
hora, e o IP é o do navegador.

Quando muda: a família troca em `/ddd` (como o `/fuso`). Efeito: a lista impressa e o texto "disque"
mudam; as ligações continuam iguais, porque a central casa pelo fim.

### 3.5 Custos, histórico, retenção

- `custos._saida` reconhece destino de 10 ou 11 dígitos além de `[89]+ID`; `gasto_crianca_mes` já
  pega pelo `caller_ext`. Tetos iguais aos de hoje; sugestão do doc 19 (600 min quando houver mais
  canais) continua como decisão à parte.
- `historico.rotulos`: destino de 10/11 dígitos → apelido cadastrado na família ("Vó Lúcia"); se
  removido depois, o número formatado.
- `call_logs.callee_ext` guarda o número completo normalizado (a entrada já guarda o do chamador).
  Retenção atual cobre; `meus-dados.json` inclui `recebe` e o DDD da casa.

### 3.6 Segurança e abuso

Lista fechada: nada fora dela completa. Padrões de tamanho fixo tiram a cobrar e internacional por
construção. Cadastro recusa serviços (0300/0303/0500/0800/0900/400X) e 1XX. O menu de entrada fala
apelidos só para números com `recebe`. Nada de discador: uma ligação por vez por telefone, como hoje.
Spoof do número do chamador (doc 14) continua sendo "só toca", sem acesso a nada.

## 4. UX, UI e textos

Regras herdadas (doc 11): uma só família tipográfica (Atkinson), branco e coral, sem details fechado
para o que todos precisam ver, ação no cabeçalho do bloco, formulário em página própria, três
tamanhos no máximo, o que exige resposta vem primeiro, sem travessão, minutos e não dinheiro.

### 4.1 Aba "Telefones" (era "Celulares")

Mesmo endereço (`/crianca/<id>/celulares` redireciona para `/crianca/<id>/telefones`), mesmo lugar na
barra (entre Ligações e Telefone; o ícone `bi-phone` passa a `bi-telephone-forward` para não confundir
com a aba Telefone, que é o aparelho). Ordem dos blocos, do que mais importa para o que menos:

```
┌─────────────────────────────────────────────┐
│ Telefones da família                        │
│ Para quem ana01 liga, além dos amigos.    │
│                                             │
│ ▌Salve os dois números nos contatos... (já) │
│ ▌Este mês: usou 12 min, restam 288   (já)   │
│                                             │
│ Celulares de casa            Adicionar (2)  │  <- h2 com linha grossa
│ Mãe   (11) 98765-4321   disque 9726310#     │  <- linhas, não cartões
│ Pai   (11) 91111-1111   disque 8726310#     │
│                                             │
│ Outros telefones         Adicionar telefone │  <- h2 + botão coral
│ Vó Lúcia   (11) 3456-7890                   │
│   disque 3456 7890#        · liga p/ ana01│
│ Casa do Théo (19) 3333-4444                 │
│   disque 19 3333 4444#     · liga p/ ana01│
│ Padaria    (11) 2222-3333                   │
│   disque 2222 3333#        · só ana01 liga│
│ 17 vagas.                                   │
│                                             │
│ Como ana01 disca                          │  <- h2
│ DDD da casa: 11 (São Paulo)        Trocar   │
│ Número do mesmo DDD: só o número e #.       │
│ De outro DDD: o DDD e o número, sem o 0.    │
│ Imprimir a lista para deixar perto do       │
│ telefone                                    │
└─────────────────────────────────────────────┘
```

Detalhes:

- Cada linha de "Outros telefones": nome em negrito, número formatado em cinza, embaixo o que a
  criança disca na caixa `discar-caixa` (o mesmo componente do 9+ID) e a marca de entrada como texto
  ("liga para ana01" / "só ana01 liga"), com um link discreto "mudar" e "remover" à direita, como
  na aba Amigos.
- Dígitos agrupados para leitura: `3456 7890#` e `19 3333 4444#` (grupos de 2 e 4, sem hífen, porque
  hífen não existe no teclado). Observação para depois: o 9+ID aparece hoje sem espaço
  (`9726310#`); vale unificar (`9 72 63 10#`) numa revisão do cartão, não neste trabalho.
- Sem nenhum número cadastrado: o bloco "Outros telefones" mostra uma frase e o botão ("Nenhum ainda.
  Cadastre a vó, a casa de um amigo, a padaria.").
- `MAX_OUTROS = 0`: o bloco e o "Como ana01 disca" não aparecem e a página fica como hoje (chave de
  lançamento).
- Em família com mais de uma criança: "disque" mostra o ID de cada criança nos atalhos (já é assim) e
  o mesmo número para todas nos outros telefones.

### 4.2 Página "Adicionar telefone" (`/crianca/<id>/telefones/novo`)

```
┌─────────────────────────────────────────────┐
│ Adicionar telefone          Voltar          │
│ ana01 vai poder ligar para esse número.   │
│ Só o que estiver aqui completa.             │
│                                             │
│ Quem é                                      │
│ [ Vó Lúcia                               ]  │
│ Como aparece para ana01 e no visor.       │
│                                             │
│ Número                                      │
│ [ 3456 7890                              ]  │
│ Com ou sem DDD. Sem DDD, vale o 11, DDD     │
│ da casa (São Paulo). Trocar o DDD da casa   │
│                                             │
│ [x] Vó Lúcia também pode ligar para ana01 │
│     Desmarque para lojas e serviços: eles   │
│     não precisam ligar para cá.             │
│                                             │
│ [        Cadastrar        ]                 │
└─────────────────────────────────────────────┘
```

- Um campo de número só (GOV.UK), `type="tel"`, `inputmode="tel"`, `autocomplete="tel-national"`,
  aceita colado do WhatsApp (`+55 11 98765-4321`), parênteses, hífen, espaços.
- Sem DDD da casa definido (família nova, sem celular, sem IP útil): o texto de ajuda vira "Digite
  com DDD" e o formulário exige 10 ou 11 dígitos; não se inventa DDD.
- Ao salvar sem DDD, a confirmação diz o que foi entendido: "Vó Lúcia cadastrada: (11) 3456-7890.
  ana01 disca 3456 7890#." Se a família vê o DDD errado, remove e cadastra com o DDD.
- Erros, no próprio campo, com exemplo: "Digite o número com ou sem DDD, como 3456 7890 ou 19 3456
  7890"; "Esse é um número de serviço (0800, 0300, 4004), não dá para cadastrar"; "Número de outro
  país não pode ser cadastrado"; "Já está cadastrado como Vó Lúcia"; "A lista está cheia (20). Remova
  um para adicionar".
- "Quem é" vem antes do número porque é como a pessoa pensa ("vou cadastrar a vó") e porque o nome
  aparece na confirmação e no visor; limite 20 caracteres (visor do GRP).

### 4.3 Celulares de casa

Formulário próprio também (`/crianca/<id>/telefones/novo-celular`), igual ao de hoje, movido para
fora da aba conforme a regra "formulário em página própria". A troca de ordem 9/8 fica no bloco.

### 4.4 Página "DDD da casa" (`/ddd`, no molde do `/fuso`)

```
┌─────────────────────────────────────────────┐
│ DDD da casa                 Voltar          │
│ É o DDD que ana01 não precisa discar e o  │
│ que vale quando você cadastra um número sem │
│ DDD.                                        │
│                                             │
│ Pelo telefone de ana01, a casa parece     │
│ estar em São Paulo, SP (DDD 11).            │  <- ou "pelos celulares de casa"
│                                             │
│ DDD  [ 11 ▾ ]  São Paulo e região           │
│                                             │
│ [ Salvar ]                                  │
└─────────────────────────────────────────────┘
```

- Select com os 67 DDDs e um rótulo ("11 São Paulo e região", "19 Campinas e região"); o rótulo
  é a capital ou a maior cidade do DDD no CSV.
- A frase de origem muda com a fonte: "pelos celulares de casa", "pelo telefone de ana01", "pelo
  seu acesso agora". Raio grande: "parece estar perto de". Sem nenhuma pista: só o select.

### 4.5 Cartão e lista impressa

O cartão de hoje ganha uma seção "Telefones de casa" depois dos amigos: nome e o que discar, com o
mesmo `td.ext`. Para listas longas, a página imprime em duas colunas. A dica do rodapé passa a: "Para
ligar: tire do gancho, disque o número e aperte #. Número de outro DDD: disque o DDD antes, sem o 0."

### 4.6 Sons novos (Piper, `voz.py`)

- `nao-esta-na-lista-de-casa`: "Esse telefone não está na lista de casa. Peça para cadastrar no site."
- `disque-com-ddd`: "Esse número existe em dois DDDs na sua lista. Disque com o DDD."
- Entrada ambígua: "Para a" + apelido + "tecle 1" (frases "para-a" e "tecle-1" a "tecle-9"; o
  apelido já existe para os grupos).

### 4.7 Textos do site

- Perguntas da capa: "Dá para ligar para celular ou telefone comum?" → "Para os telefones que a
  família cadastrar: os celulares de casa, a vó, a casa de um amigo, a padaria. A criança disca o
  número, com DDD quando é de outra cidade. Nenhum outro número completa, nem para fora nem para
  dentro."
- `por_dentro.html` (página técnica): um parágrafo sobre a lista e o DDD da casa; o teste
  `test_por_dentro` confere os arquivos citados.
- `privacidade.md`: "Dos telefones que a família cadastra (celulares de casa, parentes, amigos,
  lugares): número e nome; e o DDD da casa, estimado pela localização aproximada do endereço de
  internet do telefone e confirmado por você." Termos: só depois do sim do Daniel.
- E-mail para as famílias já ativas quando lançar: três linhas, com o link da aba.

## 5. Mudanças no código, arquivo por arquivo

| Arquivo | Mudança |
|---|---|
| `rede/dados/municipios.csv`, `rede/dados/LICENCA-municipios.txt` | base (MIT) |
| `rede/ddd.py` (novo) | `DDDS` (67), `ROTULOS` (DDD → "São Paulo e região"), `carregar_municipios()`, `por_ip(ip, cfg)`, `sugerir(conn, familia_id, ip_navegador)`, `formatar_discagem(numero, ddd_casa)` → "3456 7890" ou "19 3456 7890" |
| `rede/geoip.py` | `registro(ip, cfg)` devolvendo cidade, UF, lat/lon, raio (hoje só o fuso) |
| `rede/ids.py` | `classificar_discado`: `externo_local`, `externo`; aceitar 0 e 55 na frente |
| `rede/db.py`, `deploy/codigo.sh` | `familias.ddd`, `familias.ddd_origem`, `familia_telefones.recebe` |
| `rede/config.py` | `MAX_OUTROS` (`REDE_MAX_OUTROS`, padrão 20) |
| `rede/servicos/familia_telefones.py` | `normalizar(numero, ddd_casa=None)` aceita 8/9 dígitos com DDD da casa e recusa serviços; `adicionar(..., recebe=True, posicao=None)`; `listar_outros`; `casar_discado(conn, familia_id, tipo, digitos, ddd_casa)`; `familias_por_numero`; `decidir_entrada` com `ambiguo` |
| `rede/servicos/contas.py` | `definir_ddd(conn, familia_id, ddd, origem)` |
| `rede/servicos/chamadas.py` | `decidir_externo`; `decidir` roteia os tipos novos |
| `rede/servicos/custos.py` | `_saida` reconhece 10/11 dígitos |
| `rede/servicos/historico.py` | rótulo dos números externos |
| `rede/voz.py` | frases novas |
| `agi/check_call.py` | nada além do que `decidir` já devolve (conferir `FAMILIA_*`) |
| `agi/check_entrada.py` | `ENTRADA_OPCOES` para o menu |
| `deploy/asterisk/extensions.conf` | padrões de 8 a 13 dígitos → `Gosub(saida-tronco,s,1(${EXTEN}))`, bloco de saída único para 9/8+ID e externos; `[tronco-entrada]` ramo `AMBIGUO` com `Read` |
| `rede/web/familia.py` | rotas `telefones`, `telefones/novo`, `telefones/novo-celular`, `telefones/<id>` (mudar recebe, remover), `/ddd`; redirecionamento de `celulares` |
| templates | `telefones.html`, `telefone_novo.html`, `celular_novo.html`, `ddd.html`, `cartao.html`, `base.html` (aba), `landing.html`, `por_dentro.html` |
| `rede/textos/privacidade.md` | parágrafo (versão nova da política, com data) |
| testes | `test_ddd.py` (67 DDDs, capitais, por_ip com registro falso, sugerir nas 5 fontes, formatar_discagem), `test_familia_telefones.py` (normalizar com DDD da casa, serviços recusados, casar_discado nos 4 casos, recebe, ambiguidade de entrada, limite 20), `test_amizades_chamadas.py` (decidir_externo), `test_custos.py` (saída externa conta), `test_fluxo_familia.py` (páginas), `test_log_call.py` (callee de 11 dígitos), `test_por_dentro.py` |

Fora do telefone: nada. Fora do Asterisk: só `extensions.conf` (`dialplan reload` pelo
`deploy/tronco-vono.sh`, sem reiniciar) e dois sons.

## 6. Etapas, provas e lançamento

Estado em 13/11/2026 (fim do dia): **A, B, C e D no ar e provadas** (B31 partes 1 e 2; 168 testes;
política de privacidade 2026-11-b). Pendente: provar um fixo pela Vono. Dicção: apelidos regerados mais devagar e campo
opcional "como a criança é chamada" (`criancas.nome`, voz e telas da família; política 2026-11-c), publicados
em 13/11 à tarde. `REDE_MAX_OUTROS` no padrão 20.

| Etapa | Entrega | Prova | Tempo |
|---|---|---|---|
| **A. Base e DDD** | `municipios.csv`, `ddd.py`, `geoip.registro`, colunas novas, `/ddd` | testes; no servidor, `ddd.por_ip` nos 11 IPs da seção 2.3 e nos IPs dos telefones das famílias do piloto (sem registrar aqui) | meio dia |
| **B. Saída** | `classificar_discado`, `normalizar`, `casar_discado`, `decidir_externo`, dialplan, custos, histórico, som "não está na lista de casa" | **B31 parte 1**: do GRP do Daniel, com um fixo real e um celular de terceiro cadastrados: 8 dígitos, 9 dígitos, com DDD, com 0, com 55, número fora da lista; `call_logs.tronco = vono`, áudio nos dois lados; fixo pela Vono é inédito (B30 só provou celular) | um dia |
| **C. Site** | aba Telefones, Adicionar telefone, Adicionar celular, cartão, textos, e-mail | capturas em 390 e 1280 das quatro telas (regra do doc 11); a família do Daniel usa por dois dias | um dia |
| **D. Entrada** | `recebe`, `familias_por_numero`, menu pelos nomes, frases Piper | **B31 parte 2**: número com `recebe` toca com o nome; sem `recebe` ouve inválido; mesmo número em duas famílias ouve o menu, tecla 1 e 2, não tecla nada | meio dia |
| **E. Lançamento** | `REDE_MAX_OUTROS=20` no servidor, e-mail às famílias ativas, convite à Maria para testar vó e padaria | uma semana de uso; olhar bloqueios `EXTERNO_FORA_DA_LISTA` e `EXTERNO_AMBIGUO` no painel | |

Depois, cada um com decisão própria: B32 agenda no visor do GRP; saída aberta (doc 19, 4); teto de
600 min e mais canais na Vono; 190/192/193 (item 26).

## 7. Riscos e o que fazer com cada um

| Risco | Efeito | Mitigação |
|---|---|---|
| DDD estimado errado | número cadastrado sem DDD entra com DDD errado; a ligação cai em "não está na lista" ou, pior, a criança disca o número local e a central casa pela lista com o número errado cadastrado | a confirmação mostra o número entendido com DDD; a origem da sugestão aparece; celulares de casa têm prioridade sobre o IP; corrigir é remover e cadastrar |
| Pausa no meio do número | aparelho envia 6 dígitos como ID | já existe hoje; `#` no cartão; não mudar os 4 s |
| Vono com fixo | formato ou tarifa diferente para fixo | B31 parte 1 antes de qualquer tela; Nvoip de reserva já disca fixo |
| Lista cresce e o cartão fica longo | criança não acha | duas colunas na impressão; ordem alfabética; limite 20 |
| Família sem DDD e sem pista | formulário exige DDD | texto claro; nada inventado |
| Dois números com a mesma parte local | ambiguidade | DDD da casa decide; senão, pede o DDD |
| Terceiro cadastrado sem saber | privacidade | igual aos celulares de hoje; política atualizada; `recebe` desligável; advogado (item 13) |

## 8. Decisões do Daniel (13/11/2026)

1. Casar pelo fim do número na lista; o DDD da casa só desempata. **Sim.**
2. Fonte do DDD: celulares de casa antes do IP. **Sim.**
3. Aba passa a se chamar "Telefones". **Sim.**
4. "Quem é" antes do número no formulário. **Sim.**
5. Dígitos agrupados com espaço no "disque". **Sim.**
6. Começar pela saída, com ligação real, antes das telas. **Sim.**
7. Emergência (190, 192, 193) continua fora, como hoje (item 26 do doc 08). **Sim.**

## 9. Fontes (vistas em 12/11/2026)

- Base de municípios com DDD: <https://github.com/kelvins/municipios-brasileiros> (CSV
  `csv/municipios.csv`, licença MIT)
- Anatel, Plano de Numeração Brasileiro: <https://www.anatel.gov.br/setorregulado/plano-de-numeracao-brasileiro>;
  Resolução 749/2022: <https://www.legisweb.com.br/legislacao/?id=428952>; Resolução 358/2004 (códigos
  de emergência 100, 128, 180 a 199): <https://www.legisweb.com.br/legislacao/?id=100772>; página dos
  Serviços de Utilidade Pública e de Emergência (captcha em 12/11):
  <https://www.gov.br/anatel/pt-br/regulado/numeracao/codigos-nacionais/servicos-de-utilidade-publica-e-de-emergencia>
- Faixas de prefixo, DDDs, 9090, não geográficos: <https://pt.wikipedia.org/wiki/N%C3%BAmeros_de_telefone_no_Brasil>
- BrasilAPI, cidades por DDD: <https://brasilapi.com.br/api/ddd/v1/19>
- Grandstream GRP260x, guia de administração (Dial Plan, No Key Entry Timeout, Key as Send):
  <https://documentation.grandstream.com/knowledge-base/grp260x-series-administration-guide/>; relato
  de que o aparelho não disca na hora ao casar a regra: <https://www.3cx.com/community/threads/gxp2110-dial-plan-help.22572/latest>
- MaxMind, precisão da geolocalização por IP: <https://blog.maxmind.com/2021/07/how-accurate-is-ip-geolocation/>
  e <https://support.maxmind.com/hc/en-us/articles/4414877149467-IP-Geolocation-Data>
- GOV.UK Design System, "Telephone numbers": <https://design-system.service.gov.uk/patterns/telephone-numbers/>
- Tin Can (contatos aprovados, Party Line): <https://tincan.kids/pages/connection>; decisão do FCC
  sobre o serviço de lista fechada: <https://docs.fcc.gov/public/attachments/DA-26-381A1.pdf>
