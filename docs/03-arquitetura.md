# 03 — Arquitetura: o que muda em relação ao projeto atual

## Visão geral

```
[Celular/PC da família] --HTTPS--> [nginx] --> [Portal Flask] --> [PostgreSQL]
                                                   |                  ^   ^
                                [Telefone] --HTTPS /p/<token>/cfgMAC.xml   |   |
                                      |                                    |   |
                                      +--SIP/TCP--> [Asterisk] --realtime--+   |
                                                        \--AGI check_call.py---+
                                                        \--AGI log_call.py-----+
```

A forma é a mesma do projeto atual. As diferenças estão em cinco pontos.

## 1. Ramais dinâmicos (PJSIP realtime)

Hoje: cada ramal é uma seção no `pjsip_wizard.conf`, e adicionar exige
`systemctl restart asterisk` (lição 4), o que derruba as conexões TCP de todos
os telefones. Inaceitável numa rede com cadastro a qualquer hora.

Rede aberta: Asterisk lê endpoint, auth e AOR direto do banco (Asterisk
Realtime Architecture via ODBC). Um `INSERT` cria o ramal; o Asterisk busca o
objeto quando o telefone tenta registrar. Sem reload, sem restart.

- Tabelas `ps_endpoints`, `ps_auths`, `ps_aors`, `ps_contacts` (esquema oficial
  via alembic do Asterisk, `contrib/ast-db-manage`; o protótipo traz um
  subconjunto comentado).
- `sorcery.conf` mapeia os objetos para realtime; `extconfig.conf` mapeia as
  tabelas; `res_odbc.conf` + `odbc.ini` apontam para o Postgres.
- Transportes continuam em `pjsip.conf` (estático; não mudam).
- Cache de sorcery desligado no início (rede pequena). Se ligar depois, o
  portal chama `pjsip reload` ou o flush de cache via AMI ao alterar um ramal.
- Fonte: [Setting up PJSIP Realtime](https://docs.asterisk.org/Configuration/Channel-Drivers/SIP/Configuring-res_pjsip/Setting-up-PJSIP-Realtime/).

Banco: trocar SQLite por **PostgreSQL**. Motivos: o realtime do Asterisk via
ODBC funciona melhor com Postgres; o portal, os AGIs e o Asterisk gravam ao
mesmo tempo (o SQLite já exigiu malabarismo de permissões, lição 11); e
backup/replicação ficam triviais. O esquema do portal muda pouco.

## 2. Numeração: IDs de 6 dígitos

Hoje: ramais de 3 dígitos escolhidos pelo admin (067, 001...), celulares da
família em 9XXX/8XXX, chamada aberta em 0XXX, hora certa em 100.

Rede aberta: o ID nasce no cadastro, aleatório, **6 dígitos começando por 2 a 7**
(600 mil IDs). A criança disca o ID + #. Os prefixos ficam reservados:

| Discado | Significado | Padrão no dialplan |
|---|---|---|
| `1XX` | serviços (100 = hora certa, outros futuros) | `_1XX` |
| `[2-7]XXXXX` | ligar para uma criança | `_[2-7]XXXXX` |
| `0[2-7]XXXXX` | abrir chamada em grupo com uma criança | `_0[2-7]XXXXX` |
| `9[2-7]XXXXX` | celular 1 da família da criança | `_9[2-7]XXXXX` |
| `8[2-7]XXXXX` | celular 2 da família | `_8[2-7]XXXXX` |

Por que aleatório: evita que alguém "varra" IDs sequenciais mandando pedidos
de amizade a esmo. Por que 6 e não 4 ou 5: 6 dígitos cabem com folga na
memória de uma criança (é menos que um celular) e deixam espaço para a rede
crescer sem renumerar. O ID impresso para a criança pode ser escrito
"34 56 78" para facilitar.

A lógica dos AGIs (`check_call.py`, `check_group.py`, `log_call.py`,
`conf_leave.py`) não muda: só o padrão de extensão e a função que reconhece
"ramal de família" (hoje `len(ext) == 4 and ext[0] in ('9','8')`).

## 3. Cadastro, apelido e amizades

Hoje: o admin cria o device com código de registro; o pai ativa com o código;
contatos são autorizados listando **todos** os outros devices da rede (a tela
de contatos mostra todo mundo).

Rede aberta:

- **Conta da família**: e-mail verificado (como hoje), senha, nome. Uma conta
  pode ter várias crianças/telefones (já suportado).
- **Criança**: apelido (único na rede, 3 a 20 caracteres, letras minúsculas,
  números e `_`; sem sobrenome, sem data) e ID gerado. O apelido vira o
  `callerid` SIP (aparece no visor do telefone de quem recebe) e o nome nas
  telas dos pais autorizados. Não é buscável.
- **Amizade**: a família digita o ID do amigo. O site mostra só o apelido para
  confirmar ("adicionar `jose07`?") e envia o pedido à outra família, que
  aceita ou recusa no portal (ou por link no e-mail, como hoje). Estados:
  pendente, aceita, recusada, bloqueada. É a mesma tabela `permissions` de
  hoje, só que com pedido explícito em vez de duas autorizações soltas.
- **A tela de contatos deixa de listar a rede inteira.** Mostra só amizades e
  pedidos.
- Limites: 10 pedidos pendentes por criança; 20 pedidos por dia por conta;
  pedido recusado duas vezes vira bloqueio silencioso.
- **Código de ativação** continua existindo para os kits da ONG (caminho A).
  Quem compra por fora não precisa de código: cria a conta e baixa a
  configuração (caminho B) ou cadastra MAC + serial (caminho C).

## 4. Portal

Mesmo Flask + Bootstrap, reorganizado em torno de três telas: **Contatos**
(amizades e pedidos), **Horários**, **Histórico**; mais **Telefone** (estado do
aparelho, reconfigurar, baixar configuração, MAC/serial) e **Família** (celulares,
Groundwire; já existe).

Novidades importantes:

- **Estado do telefone**: "registrado desde 14:32", "buscou configuração às
  14:30, ainda não registrou (verifique o cabo)", "nunca se conectou". Vem dos
  logs do endpoint de provisionamento e da tabela `ps_contacts`. Corta a
  maior parte dos chamados de suporte.
- **Diagnóstico guiado**: se buscou configuração mas não registrou, o portal
  sugere SIP ALG / reiniciar roteador; se nunca buscou, sugere cabo/tomada.
- **Painel da ONG** (admin): kits preparados e seu estado, contas, denúncias,
  bloqueio, métricas (cadastros, telefones ativos, chamadas por dia), exportar.
- **PWA** (ícone na tela inicial do celular, notificação de pedido de amizade):
  barato de fazer com o site atual e substitui um "app" de verdade.
- Textos legais: termos, política de privacidade, canal de denúncia (doc 05).

## 5. Dialplan e sons

Igual ao `extensions.conf.new` atual com os padrões de 6 dígitos (esboço em
`prototipo/asterisk/extensions-rede-aberta.conf`). Mensagens de voz
reaproveitadas. Uma mensagem nova: "este número não está na sua lista de
amigos" em vez de "sem permissão", porque na rede aberta o caso comum é o ID
existir mas não haver amizade.

## Capacidade e infraestrutura

- Servidor: Oracle Cloud free tier ainda serve, mas na forma **Ampere A1** (até
  4 OCPU e 24 GB, grátis), não a E2.1.Micro atual. Asterisk sem transcodificação
  (todos em G.722/PCMU) gasta pouca CPU; 4 OCPU aguentam centenas de chamadas
  simultâneas. Uma rede de 2.000 crianças dificilmente passa de 50 chamadas
  simultâneas no pico.
- Banda: uma chamada G.722 usa cerca de 90 kbit/s por sentido por perna. 50
  chamadas simultâneas = ~9 Mbit/s. O free tier dá 10 TB/mês de saída.
- Postgres no mesmo servidor no início; separar quando fizer sentido.
- Backup diário do banco para object storage (free tier tem 20 GB).
- Monitoramento: o mínimo é um `healthcheck` externo (UptimeRobot ou similar)
  no portal e no SIP, mais alerta por e-mail se o número de ramais registrados
  cair abruptamente. Prometheus/Grafana só quando houver quem olhe.
- Segunda instância (outra região, outra ONG): é só rodar o mesmo
  `setup-servidor.sh` adaptado. Federação entre instâncias (criança da rede X
  ligar para criança da rede Y) fica fora do escopo por enquanto; SIP permite,
  mas a autorização mútua entre portais diferentes é um projeto à parte.

## O que não muda

Transporte SIP em TCP, `external_media_address`, firewall, AGIs, ConfBridge,
mensagens de voz, Groundwire para os pais, `setup-servidor.sh` como base da
instalação. As lições aprendidas do CLAUDE.md continuam valendo todas.
