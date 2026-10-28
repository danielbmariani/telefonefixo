# 09 — Plano detalhado: Caminho 3 (zero-touch) com auditoria em cada etapa

Decisão (23/10/2026): o caminho padrão para conectar o telefone é o zero-touch
pela nuvem da Grandstream. A família digita dois códigos da etiqueta no site,
liga o telefone e ele se configura sozinho. Kits preparados pela ONG estão
descartados (dão trabalho à ONG). O arquivo de configuração fica só como
último recurso para famílias com alguém técnico.

Este documento é o plano de execução. Para cada etapa do fluxo: o que
acontece, o que fica registrado, como se verifica que deu certo, o que pode
falhar e o que cada lado vê. "Auditoria" aqui significa: **toda etapa deixa um
registro que não pode ser apagado, com ator, horário, origem e resultado, e
existe uma verificação automática que confere se o estado real bate com o
registrado.**

## 0. Mudança de premissa: o telefone

A pesquisa trouxe um fato que muda o hardware: **o GXP1610 não é suportado pelo
GDMS**. A lista oficial de aparelhos do GDMS diz "GXP21XX only, pending for
other GXP models", e relatos de integradores dizem que os GXP16xx não serão
suportados (processador fraco). O zero-touch depende do GDMS. Logo:

| Modelo | GDMS/zero-touch | Preço BR (out/2026) | Papel |
|---|---|---|---|
| GRP2601 / GRP2601P | Sim, nativo (linha feita para isso) | ~R$ 300 (Magazine Luiza; Kabum tem o 2601P com código Anatel) | **Telefone de referência do caminho 3** |
| GRP2602W (Wi-Fi) | Sim | R$ 490 a 510 (importação) | Opcional, para casa sem cabo perto. Atenção: a família precisa escolher a rede Wi-Fi e digitar a senha no menu do telefone antes de ele chegar na internet. É um passo a mais, pelo teclado do aparelho |
| GXP1610 | Não (a confirmar na bancada, mas a documentação indica que não) | R$ 160 a 300 | Só pelo arquivo de configuração (último recurso). Continua suportado pelo código atual |

Fontes: [lista de aparelhos GDMS](https://documentation.grandstream.com/?p=14142), [fórum Vodia sobre GXP16xx](https://forum.vodia.com/topic/16931-grandstream-gdms-and-vodia/), [Kabum GRP2601P](https://www.kabum.com.br/produto/1069746/telefone-ip-grandstream-grp2601p-2-linhas-poe-audio-hd-conferencia-voip-escritorio-profissional), [Magazine Luiza](https://m.magazineluiza.com.br/busca/grandstream+2/), [datasheet GRP2601 em português](https://www.grandstream.com/hubfs/Product_Documentation/Datasheet_GRP2601_Portuguese.pdf).

Consequências:
- O custo para a família sobe de ~R$ 200 para ~R$ 300. Ainda abaixo do Tin Can.
- O GRP2601 tem senha de administrador aleatória de fábrica (impressa na
  etiqueta). Bom para segurança; irrelevante para o caminho 3, porque ninguém
  precisa entrar na interface.
- O script atual (`configurar-telefone.sh`) não conhece a API web do GRP. Só
  importa para o fallback; não bloqueia o caminho 3.
- A validação em bancada (seção 7) é a primeira coisa a fazer, com 2 GRP2601
  comprados em lojas diferentes.

## 1. Como o zero-touch funciona por baixo

> **Atualização 23/10/2026 (bancada B06).** A referência completa da API mostrou que
> o GDMS aceita **entregar um arquivo de configuração a um aparelho por API**
> (`device/config/xml`) e **avisar por webhook** quando o aparelho fica online,
> registra ou é resetado (`subscribe/save`). O RPS não tem API. Portanto a variante
> escolhida é a **GDMS por API**: E4 `device/add` → E5 `device/config/xml` com o
> ponteiro para o nosso servidor → E7 o aparelho busca a conta SIP no nosso servidor.
> Zero cliques da ONG. O texto abaixo foi mantido para registro da análise; o que
> vale está em E5 e na seção 7. Detalhes em `bancada/B06-api-referencia.md`.

Dois serviços da Grandstream entram em cena, ambos gratuitos e na mesma
conta (GDMS):

- **RPS (Remote Provisioning Service)**: quando um telefone Grandstream liga em
  estado de fábrica, antes de qualquer coisa ele pergunta a um servidor da
  Grandstream "para onde eu vou?". Se o MAC dele estiver cadastrado numa conta
  GDMS e associado a um "RPS" (um perfil com a URL de um servidor de
  provisionamento), a resposta é a nossa URL. O telefone grava essa URL como
  `Config Server Path` e passa a buscar o `cfgMAC.xml` lá. Depois disso, a
  Grandstream sai da conversa.
- **GDMS (gerenciamento)**: alternativa em que o GDMS passa a gerenciar o
  aparelho e empurra um template com o `Config Server Path` da rede. O
  aparelho fica "online" no GDMS e segue reportando para lá.

As duas variantes resolvem o problema. A **variante RPS é a preferida**:
menos dados para a Grandstream (só MAC e serial), nenhum controle contínuo de
terceiro sobre o telefone, e nada de template para manter. A bancada confirma
se o RPS aceita associação por API ou só pela interface.

O que já está documentado e o que falta confirmar:

| Item | Situação |
|---|---|
| Autenticação na API (token OAuth; senha = SHA256(MD5(senha)); assinatura SHA256 de `&access_token=..&client_id=..&client_secret=..&timestamp=..&`, com hash do corpo antes do `&` final nos POST) | Documentado no [GDMS API Guide](https://documentation.grandstream.com/knowledge-base/gdms-api-guide/) |
| `POST /oapi/v1.0.0/device/add` com `[{deviceName, mac, sn, siteId, orgId}]`; `GET org/list`, `GET site/list`; `POST task/add` | Documentado |
| Resposta `{retCode, msg, data}`; `retCode 0` = sucesso | Documentado; códigos de erro não |
| Criar RPS em System > RPS Management (nome, protocolo HTTP/HTTPS, "Server URL", usuário/senha globais) e "selecionar os aparelhos a configurar com o RPS" | Documentado na interface ([guia GDMS](https://documentation.grandstream.com/knowledge-base/gdms-user-guide/), [fórum Grandstream](https://forums.grandstream.com/t/gdms-rps-management/56348)) |
| Endpoint de API para associar aparelho ao RPS; `device/list`; `device/delete` | **A confirmar** na referência completa em `doc.grandstream.dev/GDMS-API` (página só carrega no navegador) |
| Comportamento do GRP2601 de fábrica: consulta RPS? em quanto tempo? precisa de reset se já foi ligado antes? | **A confirmar na bancada** |
| Códigos de erro para "MAC já cadastrado em outra conta" e "serial não bate" | **A confirmar na bancada** |

Sobre os dados enviados à Grandstream: MAC, serial, nome do aparelho (usar o
ID, nunca o apelido) e, na variante RPS, nada mais. Os servidores do GDMS
ficam nos EUA (`www.gdms.cloud`) ou UE (`eu.gdms.cloud`): é transferência
internacional de dado pessoal (o MAC associado a uma família é dado pessoal
pela LGPD). Entra na política de privacidade e no contrato com a Grandstream
(termos do GDMS). A variante RPS minimiza isso.

## 2. O fluxo e a máquina de estados do telefone

```
[E1] Conta da família ──> [E2] Criança: apelido + ID ──> [E3] MAC + serial
   ──> [E4] Cadastro no GDMS ──> [E5] XML pelo GDMS (API) ──> [E6] Família liga o telefone
   ──> [E7] Telefone busca cfgMAC.xml no nosso servidor ──> [E8] Registra no Asterisk
   ──> [E9] Confirmação e teste 100# ──> [E10] Vida útil (recheck, reconfig, troca, saída)
```

Cada telefone (`devices_hw`) tem um estado. Transições só por eventos
registrados; nunca por edição manual direta no banco.

| Estado | Significa | Entra por | Sai por |
|---|---|---|---|
| `dados_informados` | família digitou MAC + serial válidos | E3 | E4 |
| `gdms_cadastrado` | GDMS aceitou o `device/add`; aguarda o `device/config/xml` | E4 | E5 |
| `aguardando_boot` | XML entregue ao GDMS (`config_enviada_em` marcado); esperando o telefone ligar, com cronômetro visível à família | E5 | E7 ou timeout |
| `config_entregue` | nosso servidor serviu o XML para esse MAC | E7 | E8 |
| `registrado` | Asterisk tem contato SIP do ramal | E8 | E10 |
| `ativo` | fez a primeira chamada (100#) | E9 | E10 |
| `erro_gdms_conflito` | GDMS recusou: MAC já pertence a outra conta | E4 | ação da família/ONG |
| `erro_dados` | GDMS recusou: MAC/serial não batem | E4 | E3 (corrigir) |
| `sem_boot` | passou do prazo sem buscar config | E6 | E7 ou suporte |
| `sem_registro` | buscou config mas não registrou em 10 min | E7 | E8 ou suporte |
| `desativado` | família removeu o telefone ou excluiu a conta | E10 | — |

Toda transição grava uma linha em `device_state_history` (de, para, evento,
ator, horário). É a espinha dorsal da auditoria.

## 3. Etapas, uma a uma

Formato de cada etapa: **O que acontece / Pré-condições / Registro / Verificação
automática / Falhas e resposta / O que a família vê / O que a ONG vê.**

### E1 — Conta da família

**O que acontece.** E-mail, senha, verificação por código de 6 dígitos (fluxo
atual), aceite dos termos e **consentimento específico para dados da criança**
em tela separada (LGPD art. 14).

**Registro** (`audit_log`): `conta_criada` (e-mail, IP, user-agent),
`email_verificado` (horário, tentativas), `termos_aceitos` (versão do texto,
hash do texto), `consentimento_crianca` (versão, hash, horário, IP). Guardar a
versão exata do texto aceito é o que permite provar, anos depois, o que a
família leu.

**Verificação automática.** Nenhuma conta sem `email_verificado` consegue
seguir para E2. Job diário: contas sem verificação há mais de 7 dias são
apagadas (e o apagamento é registrado).

**Falhas.** E-mail não chega: reenvio com limite (3 por hora) e registro de
cada reenvio. Muitas contas do mesmo IP em pouco tempo: rate limit e marcação
`suspeita_cadastro_massa` para a fila da ONG.

**Família vê:** passos com check. **ONG vê:** contas criadas por dia, taxa de
verificação, cadastros suspeitos.

### E2 — Criança: apelido e ID

**O que acontece.** Família digita o apelido; o site valida (`ids.validar_nick`)
e sorteia um ID de 6 dígitos (`ids.gerar_id`). Gera também a senha SIP (nunca
exibida) e cria as linhas `ps_endpoints`/`ps_auths`/`ps_aors` no Postgres. O
ramal existe no Asterisk a partir daqui, mas nenhum telefone tem a senha.

**Registro.** `crianca_criada` (ID, apelido, conta), `ramal_criado` (ID, hash da
senha SIP, não a senha). Apelido rejeitado também é registrado (motivo), para
calibrar as regras.

**Verificação automática.** Unicidade de ID e apelido garantida por constraint
no banco; job diário confere que todo ID em `children` tem as três linhas
`ps_*` e vice-versa (sem ramal órfão, sem criança sem ramal).

**Falhas.** Colisão de ID (improvável, tratada no sorteio). Falha ao gravar
`ps_*`: transação única com `children`; ou grava tudo ou nada.

**Família vê:** o ID em destaque ("34 56 78") e um cartão para imprimir.

### E3 — MAC e número de série

**O que acontece.** Tela "Conectar o telefone": foto da etiqueta de baixo do
GRP2601 mostrando onde estão o MAC (12 caracteres, começa com `C0:74:AD` ou
`00:0B:82`, os prefixos da Grandstream) e o S/N. Dois campos com validação em
tempo real: formato, prefixo de fabricante, dígitos repetidos, MAC já cadastrado.

**Registro.** `telefone_dados_informados` (MAC, serial, conta, criança, IP).
Tentativas rejeitadas também (`telefone_dados_rejeitados`, motivo). Um MAC
digitado por **duas contas diferentes** gera `alerta_mac_duplicado`: pode ser
erro de digitação, telefone revendido, ou alguém tentando sequestrar um
aparelho. Nunca se sobrescreve o vínculo anterior automaticamente: o segundo
pedido fica bloqueado até a fila da ONG resolver, e a primeira família é
avisada por e-mail.

**Verificação automática.** O serial é uma prova fraca de posse (está na
etiqueta, qualquer um que viu a caixa conhece). A prova forte vem em E7:
quando o telefone físico com aquele MAC busca a configuração. O estado só
avança para `registrado` quando a prova forte acontece. Até lá, o vínculo é
provisório e expira em 30 dias (`vinculo_expirado`, registrado).

**Falhas.** Formato errado: mensagem na tela, sem registrar como suspeito
(erro de digitação é normal). Mais de 10 tentativas em uma hora: bloqueio
temporário e registro.

**Família vê:** campos com check verde/vermelho; "não encontrei a etiqueta" leva
a fotos de todos os modelos suportados.

### E4 — Cadastro no GDMS

**O que acontece.** O portal chama `POST /oapi/v1.0.0/device/add` com MAC,
serial, `deviceName = ID da criança` (nunca apelido ou e-mail), `siteId` e
`orgId` fixos da rede. O cliente (`prototipo/provisionamento/gdms_client.py`)
cuida de token, refresh e assinatura.

**Registro** (`gdms_log`, separado do `audit_log` por volume): horário, endpoint,
corpo enviado (sem segredos), `retCode`, `msg`, corpo da resposta, latência,
`request_id` interno. Mais `audit_log`: `gdms_cadastro_ok` ou
`gdms_cadastro_falhou` (com `retCode`). Token e segredo **nunca** entram em
log; o cliente redige antes de gravar.

**Verificação automática.** Após `retCode 0`, se existir `device/list`, uma
leitura confirma que o MAC está na organização (confirmação independente da
escrita). Job diário de **reconciliação GDMS**: lista de MACs no GDMS versus
`devices_hw` em estado `gdms_cadastrado` ou posterior. Divergência em qualquer
direção vira alerta: MAC no GDMS sem dono no nosso banco (órfão: alguém
cadastrou pela interface sem passar pelo portal) ou MAC no banco que o GDMS
não conhece (cadastro perdido).

**Falhas e resposta.**
- `retCode` de MAC já cadastrado em outra conta: estado `erro_gdms_conflito`.
  A família vê um texto honesto: "este telefone está registrado por outra
  empresa na Grandstream; isso acontece com alguns revendedores. Peça ao
  vendedor para liberar o aparelho (MAC tal) ou use a configuração manual".
  A ONG vê o caso na fila, com o nome da loja se a família informar. Registra
  a loja para estatística: lojas com conflito recorrente entram no FAQ.
- MAC/serial não batem: estado `erro_dados`, família corrige.
- API fora do ar / token inválido: fila de retentativa com backoff (1, 5, 30
  min, 2 h), cada tentativa registrada; a família vê "estamos registrando seu
  telefone, pode levar alguns minutos" e recebe e-mail quando concluir.
- Idempotência: antes de chamar `device/add`, consultar se o MAC já está na
  organização (se houver `device/list`); se já estiver e for nosso, pular.

**Família vê:** "telefone registrado na Grandstream" com check. **ONG vê:**
taxa de sucesso do E4, conflitos por loja, saúde da API (latência, erros).

### E5 — Entrega da configuração inicial pelo GDMS

**O que acontece.** Logo depois do `device/add`, o portal chama
`device/config/xml` com um XML pequeno para aquele MAC: `P237` =
`https://prov.rede.org/p/<token>/` (token por aparelho, gerado em E3), intervalo
de recheck e as travas de menu. O GDMS guarda esse XML e o entrega ao aparelho
quando ele conecta pela primeira vez (comportamento com aparelho offline: B06b).
A conta SIP **não** vai no XML do GDMS: o aparelho a busca no nosso servidor em
E7. Assim a senha SIP nunca passa pela Grandstream e a prova de entrega fica no
nosso `prov_log`. Se a bancada (B09) mostrar que o aparelho não rebusca o P237
logo após aplicar o XML do GDMS, `REDE_GDMS_XML_CONTEUDO=completo` passa a
mandar a conta SIP também.

Sem operador. O único trabalho humano possível é o fallback: se a chamada
falhar `GDMS_MAX_TENTATIVAS` vezes (backoff 1, 5, 30, 120, 360, 720 min), o
portal abre a tarefa `enviar_config_gdms` no painel, e `flask gdms-xml <id>`
imprime o XML para o operador carregar em Dispositivo VoIP > Definir parâmetros.

**Webhook.** Uma vez, `flask gdms-eventos` registra
`SITE_URL/gdms/eventos/<segredo>` como callback e assina os eventos da
organização (deviceStatus, accountStatus, alertas 0 falha de registro, 2 reset
de fábrica, 5 reboot, 7 tarefa falhou, 9 offline). O GDMS não assina os
callbacks; a proteção é o segredo longo na URL, rate limit por IP e só aceitar
MACs que conhecemos. Cada mensagem vai para `gdms_log` e para `audit_log`
(`gdms_aparelho_online`, `gdms_conta_up`, `gdms_alerta_reset_de_fabrica`, que
abre caso). **Nenhum evento do GDMS muda o estado do telefone**: E7 e E8
continuam provados pelo nosso servidor e pelo Asterisk. O evento serve ao
diagnóstico ("o GDMS viu o aparelho online às 14:02 e ele não bateu no nosso
servidor": problema de P237/HTTPS, não de rede da família).

**Registro.** `telefone_config_enviada` (ator `sistema`, método `api`,
conteúdo `ponteiro`/`completo`, `xml_versao`), `gdms_log` com md5 e tamanho do
arquivo (não o conteúdo). Fallback: `gdms_config_retentativa`,
`tarefa_operador_criada`, `tarefa_operador_concluida` com tempo decorrido.

**Verificação automática.** `device/account/status` e o webhook mostram o que
o GDMS vê; a reconciliação diária compara `config_enviada_em` com
`gdms_online_em` e abre caso quando o aparelho ficou online no GDMS mas não
apareceu em E7 em 30 min.

**Família vê:** "pode ligar o telefone" imediatamente após E4, por e-mail e na
tela.

### E6 — A família liga o telefone

**O que acontece.** Instrução: "conecte o cabo de rede no roteador e a fonte
na tomada; se o telefone já foi usado antes, faça o reset de fábrica (menu
tal)". O telefone boota, consulta o RPS da Grandstream, recebe a URL da rede.
Nós não enxergamos essa etapa; enxergamos a próxima.

**Registro.** `familia_informou_ligado` (botão "já liguei" no portal, com
horário) para medir o tempo entre ligar e E7.

**Verificação automática.** Cronômetro no portal: se em 3 minutos não houver
E7, mostrar "desligue e ligue de novo"; em 10 minutos, "faça o reset de
fábrica" com passo a passo; em 30 minutos, estado `sem_boot` e oferta de
contato com o suporte, com o caso já aberto na fila da ONG contendo todo o
histórico (dados informados, resposta do GDMS, horários).

**Falhas típicas**: telefone já usado (sem reset não consulta o RPS); sem
internet no cabo; MAC digitado de outro aparelho (o telefone que bootou tem
outro MAC: nunca vai bater); telefone não suportado pelo RPS. Para cada uma,
texto específico no portal.

### E7 — O telefone busca a configuração no nosso servidor

**O que acontece.** `GET https://prov.rede.org/p/<token>/cfg<mac>.xml`. O
servidor valida: token existe e está ativo; MAC da URL é o MAC vinculado ao
token; estado permite entrega. Se tudo bate, gera o XML (`grandstream_xml.py`)
com as credenciais SIP, o apelido, a URL de provisionamento (P237 com o
token) e as travas do aparelho, e entrega. Marca a **prova de posse**: aquele
MAC, fisicamente, falou com a gente.

**Registro** (`prov_log`): horário, IP de origem, user-agent (traz modelo e
firmware), MAC pedido, token, resultado (`entregue`, `token_invalido`,
`mac_nao_bate`, `estado_invalido`), versão do XML servida, hash do XML.
`audit_log`: `config_entregue` na primeira vez e `config_reentregue` nas
seguintes. Toda requisição recusada é registrada e conta para rate limit.

**Verificação automática.**
- Dois MACs diferentes usando o mesmo token: alerta `token_compartilhado`,
  token revogado, família avisada.
- Mesmo MAC vindo de dois IPs públicos muito distantes no mesmo dia: alerta
  (telefone clonado? dados vazados?), sem bloquear automaticamente.
- User-agent com firmware desconhecido: registrar para a tabela de
  compatibilidade.
- Nunca entregar XML para MAC em estado `desativado` ou `erro_*`.

**Falhas.** Telefone pede `cfg<mac>.xml` com MAC que não bate com o token:
provável erro de digitação em E3. O portal mostra à família "um telefone com
o MAC `C0:74:AD:..` tentou se conectar; o que você digitou foi `..`. É o
mesmo aparelho? Corrigir". Corrigir gera novo `telefone_dados_informados`,
novo E4 (o GDMS tem o MAC errado), tudo registrado.

**Família vê:** check "telefone buscou a configuração às 14:32". **ONG vê:**
funil E5→E7 (quantos ligam e em quanto tempo), firmwares em campo.

### E8 — O telefone registra no Asterisk

**O que acontece.** O aparelho aplica o XML, reinicia e faz REGISTER com ID e
senha. O Asterisk grava em `ps_contacts`. O portal observa a tabela (ou os
eventos AMI `ContactStatus`) e muda o estado para `registrado`.

**Registro.** `sip_registrado_primeira_vez` (ID, IP de origem, user-agent SIP
com firmware, horário). Depois, só mudanças relevantes: `sip_perdeu_registro`
por mais de 1 hora, `sip_registrou_de_ip_novo`.

**Verificação automática.**
- IP público do REGISTER deve ser o mesmo IP do E7 (mesma casa). Diferente:
  alerta leve (pode ser IP dinâmico mudando; dois eventos seguidos é
  suspeito).
- Registro de um ID cujo telefone está em estado anterior a `config_entregue`:
  impossível pelo fluxo; se acontecer, alerta grave (`credencial_vazada`),
  senha SIP rotacionada automaticamente e caso aberto.
- Job de 5 em 5 minutos: `ps_contacts` × `devices_hw`; alimenta "online/offline"
  no portal e a métrica "telefones online agora".

**Falhas.** Buscou config, não registrou em 10 min: estado `sem_registro`.
Causas típicas: SIP ALG do roteador (TCP ajuda, mas há roteadores piores),
porta bloqueada, firmware que exigiu reboot a mais. Portal mostra roteiro:
desligar/ligar, reiniciar roteador, desativar SIP ALG (fotos dos roteadores
mais comuns no Brasil).

**Família vê:** check "telefone conectado". **ONG vê:** funil E7→E8, taxa de
`sem_registro` por modelo/firmware/provedor de internet (o IP revela o
provedor; útil para o FAQ).

### E9 — Confirmação e primeira chamada

**O que acontece.** Portal: "Tire do gancho e disque 100#". O dialplan atende
na hora certa; `log_call.py` grava. Estado `ativo`.

**Registro.** `primeira_chamada` (ID, destino, duração). A partir daqui o
`call_logs` do projeto atual é a trilha.

**Verificação automática.** Telefones `registrado` que não fazem a chamada de
teste em 48 h recebem e-mail lembrando (a instalação pode ter parado antes do
fim; é dado para o funil).

### E10 — Vida útil

- **Rechecagem periódica.** O telefone volta a pedir o XML no intervalo
  configurado (P193). Cada pedido vai para `prov_log`. Serve como "batimento
  cardíaco" do provisionamento e permite empurrar mudanças (apelido novo,
  nova trava) sem a família fazer nada.
- **Reconfigurar** (portal): gera senha SIP nova, incrementa a versão do XML;
  registra `reconfiguracao_solicitada` (ator: família ou operador, motivo). O
  telefone pega na próxima checagem ou ao religar.
- **Trocar o telefone** (mesmo ID, MAC novo): novo E3→E8 com o ID existente;
  o MAC antigo vai para `desativado` e sai do GDMS (`device/delete`, se
  existir; senão tarefa de operador). Registrado.
- **Remover telefone / excluir conta**: revoga token, apaga `ps_*`, e (desde 28/10/2026, automático
  pela `gdms_fila`, etapas `zerar` e `remover_gdms`) manda ao aparelho a configuração de fábrica
  (`grandstream_xml.pvalues_fabrica`), pede o reset pela API (`task/add` tipo 2, não comprovado na
  B11) e três minutos depois tira o MAC do GDMS (`device/delete`). Tarefa de operador só se o
  `device/delete` falhar `GDMS_MAX_TENTATIVAS` vezes. Mantém no `audit_log` apenas o necessário (ID, MAC em hash, datas),
  apaga o resto conforme a tabela de retenção do doc 05. `conta_excluida`
  registrado com o que foi apagado e o que foi retido e por quê.
- **Reset de fábrica pela família** (telefone volta a perguntar ao RPS): se o
  aparelho continua associado ao RPS, volta sozinho. Se foi removido do GDMS,
  o portal tem o botão "reativar telefone", que refaz E4/E5 com os dados já
  guardados. Registrado.

## 4. Modelo de dados da auditoria

Quatro tabelas, todas **append-only**: o papel de banco usado pelo portal tem
`INSERT` e `SELECT`, sem `UPDATE`/`DELETE`. Correção é uma nova linha
apontando para a anterior (`corrige_id`), nunca edição.

```
audit_log            eventos de negócio (quem fez o quê)
  id, ts, request_id, ator_tipo (familia|sistema|operador|telefone),
  ator_id, acao, objeto_tipo, objeto_id, ip, user_agent, detalhes (jsonb),
  corrige_id

device_state_history transições de estado do telefone
  id, ts, device_id, de, para, evento, ator_tipo, ator_id, audit_id

prov_log             toda requisição ao servidor de provisionamento
  id, ts, ip, user_agent, mac_pedido, token_id, resultado, xml_versao, xml_sha256

gdms_log             toda chamada à API do GDMS
  id, ts, request_id, endpoint, metodo, corpo_enviado (redigido),
  ret_code, msg, corpo_resposta, latencia_ms, tentativa
```

Regras:
- `request_id` liga as linhas de uma mesma ação do usuário nas quatro tabelas.
- Segredos (senha SIP, token, client secret, access token) nunca aparecem;
  guarda-se hash quando precisar provar igualdade.
- Exportação diária para object storage (fora do servidor) com SHA-256 do
  arquivo registrado em outro lugar (e-mail para a ONG, por exemplo). Isso dá
  a prova de integridade: se alguém alterar o banco, o export do dia não bate.
- Retenção: `audit_log` e `device_state_history` enquanto a conta existir
  mais 1 ano (com dados pessoais minimizados após a exclusão); `prov_log` e
  `gdms_log` 180 dias.
- Acesso de leitura ao `audit_log` só para operadores da ONG com 2FA, e **a
  leitura também é registrada** (`auditoria_consultada`, quem, quando, filtro).
- Ações de operador exigem campo "motivo", gravado no evento.

Esboço SQL em `prototipo/asterisk/schema-auditoria.sql`.

## 5. Painel da ONG e verificações automáticas

**Funil de ativação** (por dia/semana): E1 → E2 → E3 → E4 ok → E5 → E7 → E8 →
E9. Cada degrau com percentual e tempo mediano. É o instrumento para descobrir
onde as famílias travam e o que melhorar no texto do site.

**Fila de casos**: `erro_gdms_conflito`, `sem_boot` > 30 min, `sem_registro`,
`alerta_mac_duplicado`, `token_compartilhado`, tarefas manuais de RPS. Cada
caso abre com a linha do tempo completa (todas as tabelas filtradas pelo
`request_id`/`device_id`). Operador resolve com motivo; tudo registrado.

**Reconciliações automáticas** (jobs com resultado registrado em `audit_log`
como `reconciliacao_executada`, com contagens e divergências):

| Job | Frequência | Confere |
|---|---|---|
| GDMS × banco | diária | MACs na organização GDMS = MACs em estado ≥ `gdms_cadastrado` |
| Asterisk × banco | diária | linhas `ps_*` = crianças ativas; nenhum `ps_contacts` para ID desconhecido |
| Estados × fatos | diária | todo `registrado` tem `ps_contacts` nos últimos 7 dias; todo `config_entregue` tem `prov_log` |
| Tokens | diária | token ativo = exatamente um telefone não desativado |
| Export de auditoria | diária | arquivo gerado, hash enviado |
| Vínculos provisórios | diária | `dados_informados` há > 30 dias sem E7 → expirar |

Qualquer divergência gera alerta por e-mail à ONG e um caso na fila. Nenhuma
divergência é corrigida automaticamente: a correção é humana e registrada.

**Métricas de saúde**: telefones online agora, chamadas hoje, latência e
taxa de erro da API do GDMS, certificado HTTPS (dias para expirar), espaço
em disco, backups.

## 6. Segurança específica do caminho

- **Conta GDMS**: no CNPJ da ONG, não de uma pessoa. Organização dedicada à
  rede (nada mais nela). 2FA em todos os usuários. Usuários nominais para
  operadores (nunca login compartilhado), porque o GDMS também tem log de
  quem fez o quê.
- **Credenciais da API**: `client_id`/`client_secret` em variável de ambiente
  do serviço (como o SMTP hoje), cofre da ONG como fonte, rotação anual ou a
  qualquer suspeita (a reaplicação invalida o segredo antigo). O usuário GDMS
  usado pela API é um usuário próprio, com o mínimo de permissão que o GDMS
  permitir.
- **Servidor de provisionamento**: HTTPS com HSTS; token de 32 bytes; MAC
  vinculado; sem listagem de diretório; rate limit por IP (um telefone pede
  uma vez por boot e uma por dia); resposta idêntica (404) para token
  inexistente e MAC que não bate, para não vazar quais tokens existem.
- **O XML carrega segredos** (senha SIP, senha admin do aparelho). Mitigações:
  TLS; token individual; a senha SIP só serve para registrar aquele ramal,
  que já é da família; rotação pelo portal a um clique; alerta de
  `token_compartilhado`.
- **Senha admin do GRP2601**: o XML grava uma senha própria por aparelho
  (gerada, guardada cifrada). A família pode pedir para vê-la no portal
  (evento `senha_admin_consultada`). A senha aleatória de fábrica deixa de
  valer.
- **Travas do aparelho** no XML: desabilitar acesso web nível usuário,
  travar menu de configuração do teclado, desabilitar
  provisionamento por DHCP opção 66 (um roteador malicioso não pode
  redirecionar o telefone), não apontar servidor de firmware externo. P-values
  exatos do GRP na bancada.
- **Bloqueio de SIP de fora do fluxo**: o Asterisk só aceita REGISTER de IDs
  existentes; `fail2ban` nos logs; limite de tentativas por IP.
- **Separação de papéis**: operador da ONG vê fila e auditoria; não vê senha
  SIP nem pode editar estados diretamente. Administrador técnico tem acesso
  ao servidor, e seus acessos SSH também são registrados (auditd ou
  equivalente simples).

## 7. Validação em bancada (fase 0) com evidências

Comprar: 2 GRP2601 de lojas diferentes (para testar o conflito de revendedor)
e, se o orçamento permitir, 1 GRP2602W (Wi-Fi) e usar o GXP1610 que já existe
para documentar que ele **não** funciona no zero-touch. Dois dias de trabalho.

Cada item abaixo gera uma evidência guardada em `rede-aberta/bancada/`
(captura de tela, trecho de log, arquivo), nomeada `B01-...`. É a auditoria
da própria validação: o que foi testado, quando, com que firmware, resultado.

| # | Teste | Evidência esperada | Decide |
|---|---|---|---|
| B01 | Criar conta GDMS no nome da ONG, 2FA, organização dedicada | captura | — |
| B02 | Aplicar para API Developer; obter client_id/secret; token via `oauth/token` com o `gdms_client.py` | resposta JSON (redigida) | o cliente do protótipo funciona |
| B03 | `org/list`, `site/list` | JSON | IDs fixos para o portal |
| B04 | XML base do site por API (`device/site/config/xml`, `applyAddDevice`) ou template por modelo: vale para travas comuns? | JSON / captura | onde ficam as travas |
| B05 | `device/add` do GRP2601 nº 1 via API | JSON `retCode 0`; aparelho na lista | API cobre E4 |
| B06 | API cobre E5? | **feito**: `device/config/xml` + webhook (`bancada/B06-api-referencia.md`) | E5 sem operador |
| B06b | `device/config/xml` com aparelho offline: aceito? entregue no primeiro boot? multipart ok? | JSON + log | E5 funciona de fábrica |
| B06c | Webhook registrado (`flask gdms-eventos`); evento `deviceStatus=1` chega no boot | `gdms_log` | diagnóstico E6/E7 |
| B07 | Servir `cfg<mac>.xml` gerado pelo protótipo num `location` HTTPS do VPS atual, com log nginx detalhado | config nginx + arquivo | — |
| B08 | Ligar o GRP2601 de fábrica. Medir tempo até a requisição aparecer no log do nginx. Conferir user-agent | linha de log com horário | **o zero-touch funciona?** tempo esperado em E6 |
| B09 | Confirmar que o aparelho aplicou: registrou no Asterisk de teste; P237 gravado (ver na interface do aparelho); menu travado | `pjsip show contacts`, capturas | P-values corretos |
| B10 | Religar o aparelho: busca o XML de novo? Em quanto tempo volta a checar? | log nginx | P193 e comportamento do recheck |
| B11 | Reset de fábrica e repetir B08 sem mexer no GDMS | log | reset não quebra a associação |
| B12 | Remover do GDMS e resetar: o que acontece? | log (nada deve chegar) | fluxo "reativar" |
| B13 | Tentar `device/add` do mesmo MAC numa segunda conta GDMS | JSON com `retCode` de erro | código do conflito para E4 |
| B14 | `device/add` com serial errado | JSON | código de erro para `erro_dados` |
| B15 | GRP2601 nº 2 (outra loja): repetir B05 e B08 | JSON + log | taxa de conflito de revendedor |
| B16 | GRP2602W: configurar Wi-Fi pelo teclado, repetir B08; cronometrar e filmar os passos | vídeo/notas | vale oferecer o modelo Wi-Fi? |
| B17 | GXP1610: `device/add` e boot | JSON + log | confirmar que não serve ao caminho 3 |
| B18 | HTTPS: certificado Let's Encrypt é aceito pelo GRP? Testar também com certificado inválido (deve recusar) | log / comportamento | segurança do E7 |
| B19 | Remover o aparelho do GDMS depois de provisionado: continua funcionando e rechecando no nosso servidor? (se sim, dá para minimizar dados na Grandstream) | log | decisão de manter ou não no GDMS |
| B20 | Ler os termos de uso do GDMS e anotar o que dizem sobre dados e localização | trecho | política de privacidade |

Saída da bancada: tabela de P-values confirmados para o GRP2601 (vai para o
`grandstream_xml.py`), códigos de erro do GDMS (vai para o `gdms_client.py`),
tempos medidos (vão para os cronômetros do portal), e a decisão `ponteiro` × `completo`
no XML do E5.

## 8. Implementação (fase 1 revisada)

Tarefas com critério de aceite de auditoria. Estimativas em dias de uma pessoa.

| # | Tarefa | Dias | Aceite de auditoria |
|---|---|---|---|
| T1 | Servidor: Oracle A1, Postgres com papéis (portal: CRUD nas tabelas de negócio, INSERT/SELECT nas de auditoria), Asterisk realtime, nginx | 3 | tentativa de `UPDATE` em `audit_log` pelo papel do portal falha |
| T2 | Esquema: negócio + auditoria + `device_state_history`; função única `transicionar(device, evento)` que grava estado e histórico na mesma transação | 2 | nenhum caminho de código muda estado sem passar por ela (teste) |
| T3 | Cadastro (E1, E2): verificação de e-mail, consentimento versionado, apelido/ID, criação do ramal em transação | 4 | eventos E1/E2 presentes e com versão do texto |
| T4 | Tela MAC + serial (E3) com validação, duplicidade, fotos | 2 | tentativas rejeitadas registradas; MAC duplicado abre caso |
| T5 | Cliente GDMS (E4): token, refresh, assinatura, retentativas, `gdms_log` redigido, tratamento dos `retCode` da bancada | 3 | nenhum segredo em log (teste grep nos logs de teste) |
| T6 | E5: `device/config/xml` por API com retentativa; webhook de eventos; fallback de tarefa | feito (portal) | B06b/B06c na bancada |
| T7 | Servidor de provisionamento (E7): endpoint, validações, XML, `prov_log`, alertas de token/MAC | 3 | toda requisição, aceita ou não, em `prov_log` |
| T8 | Observador de registro SIP (E8): leitura de `ps_contacts`/AMI, estados, alertas de IP | 2 | `sip_registrado_primeira_vez` com user-agent |
| T9 | Tela "Conectando seu telefone" com cronômetros, checks e roteiros de falha | 3 | cada roteiro mostrado é registrado (para medir eficácia) |
| T10 | Amizades por ID, horários, histórico (reaproveitar), família, exclusão de conta com cascata para GDMS e Asterisk | 5 | `conta_excluida` lista o que foi apagado/retido |
| T11 | Painel da ONG: funil, fila de casos, linha do tempo por `request_id`, consulta de auditoria registrada, motivo obrigatório | 4 | `auditoria_consultada` gravado a cada consulta |
| T12 | Jobs de reconciliação e export diário com hash | 2 | relatório diário chega por e-mail |
| T13 | Textos: termos, privacidade (inclui GDMS e transferência internacional), consentimento, moderação | externo | versões com hash no banco |
| T14 | Revisão de segurança (externa) e teste de ponta a ponta com 3 telefones | 2 | relatório na pasta `bancada/` |
| T15 | Piloto: 20 a 50 famílias que compram o GRP2601 por conta própria | 4 semanas | funil e fila sem casos sem resposta > 48 h |

Total técnico: 36 a 38 dias, mais a bancada (2) e a fase de piloto.

## 9. Riscos específicos deste caminho

| Risco | Probabilidade | Mitigação |
|---|---|---|
| `device/config/xml` não entrega a aparelho offline (só a online) | média | B06b decide; alternativas por API: `device/site/config/xml` com `applyAddDevice` (XML comum do site, sem token) ou `template/push/config` após o webhook de online; última opção: tarefa manual |
| Conflito de revendedor frequente nas lojas brasileiras | baixa a média | medir na bancada e no piloto; FAQ com lojas "limpas"; fallback do arquivo de configuração |
| GRP2601 some ou sobe de preço | baixa | linha GRP é a atual da Grandstream; manter 2 modelos homologados (2601 e 2602W) |
| Grandstream muda ou fecha o GDMS/RPS | baixa | só afeta ativações novas; telefones ativos não dependem; fallback do arquivo; monitorar anúncios |
| Família digita MAC errado e o telefone "nunca chega" | alta (erro humano) | validação por prefixo, foto da etiqueta, e o diagnóstico do E7 que mostra o MAC que realmente apareceu |
| Telefone usado (não de fábrica) | média | instrução de reset no fluxo; cronômetro sugere reset em 10 min |
| Dados de MAC/serial na nuvem da Grandstream (LGPD) | certa | XML `ponteiro` (senha SIP não passa pelo GDMS), `deviceName` = ID, política de privacidade explícita, remover do GDMS após provisionar se B19 mostrar que é seguro |
| Auditoria vira peso e ninguém olha | média | painel com fila e alertas por e-mail; reconciliação diária automática; revisão mensal de 30 minutos pela ONG com roteiro |
