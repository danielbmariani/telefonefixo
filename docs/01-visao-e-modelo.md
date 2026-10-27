# 01 — Visão e modelo

## O problema que a rede resolve

Famílias que querem adiar o celular das crianças esbarram no mesmo ponto: a
criança perde o canal de contato com os amigos. O telefone fixo tradicional
morreu, e as alternativas (celular "de criança", relógio com chip, tablet com
app) trazem tela, notificação e, em geral, um serviço fechado e pago.

O projeto atual prova que dá para ter um telefone de mesa de verdade, sem tela
de aplicativo, em que a criança disca o número do amigo e conversa, e os pais
controlam com quem e quando. Funciona há meses com seis famílias. O custo de
operação é zero (Oracle Cloud free tier) e o único investimento é o telefone.

O que impede de crescer não é tecnologia: é que cada telefone novo passa pelas
mãos do Daniel, e cada ramal novo exige mexer em arquivo de configuração e
reiniciar o servidor.

## O que a rede aberta é

Uma rede telefônica fechada para crianças, aberta para cadastro.

- **Qualquer família pode entrar.** Cria conta no site, cadastra a criança
  (apelido), recebe um ID numérico e configura o telefone.
- **Ninguém liga para ninguém sem autorização mútua.** Igual ao projeto atual:
  a família A autoriza B e a família B autoriza A. Sem isso a chamada nem toca.
- **Não existe lista de crianças.** Para adicionar um amigo é preciso saber o ID
  dele (as crianças trocam o ID como trocavam telefone). O site não permite
  buscar por apelido, e o apelido só aparece para quem já está autorizado.
- **Hardware de prateleira.** O aparelho de referência é o telefone IP
  Grandstream GXP1610: liga direto no roteador por cabo, tem um visor pequeno
  de uma linha (mostra o apelido de quem está ligando) e nada de aplicativo.
  Qualquer outro telefone IP ou adaptador SIP também funciona, e o código atual
  já suporta o adaptador HT801/HT802 para quem prefere telefone analógico.
- **Open source, sem lucro.** Código MIT (como hoje). A ONG opera a rede; o
  custo de infraestrutura é baixo e coberto por doação ou pela própria ONG.
- **Sem interligação com a rede telefônica pública.** Chamadas só dentro da rede
  (e para o celular da família via app SIP, como hoje). Isso mantém o serviço
  fora da regulação de telefonia da Anatel (ver doc 05) e evita custo por minuto.

## O telefone

| Modelo | Situação | Observações |
|---|---|---|
| **Grandstream GRP2601** (referência) | Linha atual. ~R$ 300 no Brasil (Magazine Luiza; Kabum vende o GRP2601P com código Anatel) | Feito para zero-touch via GDMS, que é o caminho escolhido (doc 09). Ethernet. Senha admin aleatória de fábrica |
| Grandstream GRP2602W | Linha atual, com Wi-Fi. R$ 490 a 510 (importação) | Elimina o cabo até o roteador, mas a família precisa digitar a senha do Wi-Fi no teclado do telefone antes de ele chegar na internet |
| Grandstream GXP1610 | Já suportado pelo script atual, mas **não suportado pelo GDMS** (fora de linha, firmware final 1.0.7.x). R$ 160 a 300 | Só pelo arquivo de configuração (último recurso). Ethernet, visor de uma linha |
| Adaptador HT801/HT802 + telefone com fio | Já suportado | Alternativa para quem já tem telefone analógico ou quer um telefone "de antigamente" |

Fontes de preço: [Kabum](https://www.kabum.com.br/produto/353118/telefone-ip-grandstream-1-linha-1-conta-sip-compativel-com-headsets-ehs-10-100-gxp1610), [Magazine Luiza](https://www.magazineluiza.com.br/marcas/grandstream/), [Onedirect UK](https://www.onedirect.co.uk/grandstream-grp2601), [Grandstream GRP2601](https://www.grandstream.com/products/ip-voice-telephony-carrier-grade-ip-phones/grp-series-essential-ip-phones/product/grp2601p).

Decisão (23/10/2026): GRP2601 como telefone de referência, porque o zero-touch
depende do GDMS e o GXP1610 não é suportado. GRP2602W como opção para casas
sem cabo perto do quarto, se a bancada mostrar que digitar o Wi-Fi no teclado
é aceitável.

Detalhe importante para um telefone de criança: o telefone IP tem menus no
próprio aparelho (configurações, histórico, agenda). O provisionamento deve
travar o que não interessa (menu de configuração, acesso web no nível
usuário) para a criança não mudar nada sem querer. Ver doc 02.

## Princípios de produto

1. **Zero tela para a criança.** Toda a interface da criança é o telefone: tirar
   do gancho, discar, falar. Mensagens de voz em português para cada situação.
   O visor do telefone só mostra quem está ligando e o número discado.
2. **Pais no controle, sem vigilância.** Os pais decidem contatos e horários e
   veem o histórico (quem, quando, quanto tempo). Não há gravação de áudio.
3. **Privado por padrão.** Conta nova não liga para ninguém. Nada é público.
4. **Simples de instalar.** Meta: família sem conhecimento técnico instala em 15
   minutos seguindo o site. Tudo que exigir conhecimento técnico é falha nossa.
5. **Barato de operar.** Um servidor pequeno atende milhares de crianças. Nada
   de dependência de serviço pago por usuário.
6. **Reproduzível.** Outra ONG ou outro país deve conseguir levantar a própria
   rede com a documentação, sem pedir nada a ninguém.

## Comparação com o Tin Can (EUA)

O Tin Can é a referência mais próxima: um telefone fixo para crianças que liga
via Wi-Fi, só para contatos aprovados pelos pais num app. Lançado em 2025,
viralizou nos EUA.

| | Tin Can | Rede aberta (proposta) |
|---|---|---|
| Hardware | Próprio (telefone com Wi-Fi ou Ethernet), US$ 75 a 100 | De prateleira: Grandstream GXP1610 (R$ 160 a 300) ou GRP2601W com Wi-Fi |
| Chamadas dentro da rede | Grátis | Grátis |
| Ligar para fora (celular, fixo) | Plano pago "Party Line", US$ 9,99/mês | Só para o celular da família, via app SIP (Groundwire), sem custo mensal |
| Controle dos pais | App próprio: contatos aprovados, horários, não perturbe | Site responsivo (PWA): contatos com autorização mútua, horários por dia, histórico |
| Chamada em grupo | Não divulgado | Sim, até 5 (já existe) |
| Caixa postal | Sim ("answering machine") | Não no MVP (ver decisões em aberto) |
| Código | Fechado | MIT |
| Quem opera | Empresa (capital de risco) | ONG, sem lucro |
| Disponível no Brasil | Não | Sim |

Fontes: [tincan.kids](https://tincan.kids/), [GeekWire](https://geekwire.com/2025/landline-inspired-phone-startup-raises-3-5m-investor-calls-it-one-of-the-most-viral-businesses-i-have-seen/), [PureWow](https://www.purewow.com/family/tin-can-landline-review), [CPR](https://www.cpr.org/2026/02/04/tin-can-kids-landline-cellphone-alternative/).

A grande diferença de modelo é o hardware. O Tin Can controla a experiência
porque fabrica o aparelho (e por isso o aparelho já sai configurado). Nós
usamos telefone de prateleira, o que barateia e abre, mas transfere para nós o
problema de configurar um telefone que não sai pré-configurado. Esse é o tema
do doc 02.

## Papel da ONG

A ONG é a operadora da rede. Isso significa quatro frentes:

1. **Infraestrutura**: manter o servidor (Asterisk + portal), domínio, e-mail,
   backup. Carga baixa depois de montado; precisa de uma pessoa técnica de
   referência (pode ser voluntária) e de um plano de contingência.
2. **Atendimento às famílias**: dúvidas de instalação, telefone que não registra,
   roteador com SIP ALG. É a maior carga de trabalho. Pode ser reduzida com
   boa documentação, FAQ no site e diagnóstico automático no portal ("seu
   telefone registrou às 14:32", "seu telefone nunca se conectou").
3. **Moderação e segurança**: canal de denúncia, bloqueio de contas, resposta a
   incidentes. Com autorização mútua obrigatória o risco é baixo, mas o canal
   precisa existir desde o dia um (e o ECA Digital exige).
4. **Logística de kits** (opcional, mas recomendado no início): comprar telefones
   em lote, pré-preparar com o endereço do servidor e enviar ou entregar às
   famílias. Reduz drasticamente o suporte na fase de piloto.

Comunicação, captação e relação com escolas são o lado forte da ONG, e é onde
a rede deixa de ser um projeto de software e vira um movimento. Uma escola em
que dez famílias aderem juntas resolve o problema do "não tenho para quem
ligar", que é a barreira real de adoção.

## Nome

Precisa de nome e domínio próprios, diferentes de "telefone-fixo.duckdns.org".
Ver doc 08.
