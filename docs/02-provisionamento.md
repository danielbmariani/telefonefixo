# 02 — Provisionamento: como o site configura o telefone

> **Atualização 23/10/2026.** Decisão tomada: **caminho C (zero-touch via GDMS)**
> é o padrão. O caminho A (kits) foi descartado por dar trabalho à ONG; o
> caminho B fica só como último recurso, porque descobrir o IP do telefone na
> rede de casa trava a maioria das famílias. O GXP1610 não é suportado pelo
> GDMS, então o telefone de referência passa a ser o GRP2601. O plano de
> execução detalhado está no **doc 09**. O texto abaixo é a análise original
> das opções e continua válido como referência.

Esta é a questão central da rede aberta. Tudo o mais já existe ou é extensão
direta do que existe.

## Por que o site não consegue configurar o telefone diretamente

Hoje o `configurar-telefone.sh` roda no notebook do Daniel, **na mesma rede
local** do telefone, e fala com a API HTTP do aparelho (`/cgi-bin/dologin`,
`/cgi-bin/api.values.post`, reboot). Um site não pode fazer o mesmo:

- O navegador bloqueia requisições de uma página pública (HTTPS) para endereços
  da rede local (`192.168.x.x`). É o mecanismo "Private Network Access" do
  Chrome, mais as regras de CORS e de conteúdo misto (HTTPS chamando HTTP).
- A API do GXP1610 não envia os cabeçalhos CORS necessários e ainda exige o
  header `Referer`, que o navegador não deixa forjar.
- Mesmo que funcionasse, a família teria que descobrir o IP do telefone e a
  senha admin, que é exatamente a parte que queremos eliminar.

Então o botão do site **não** vai "entrar" no telefone. O caminho certo é o
inverso: o telefone vai até o nosso servidor buscar a configuração. Todo
telefone IP profissional faz isso, inclusive o GXP1610; é assim que operadoras
entregam aparelhos já funcionando.

## O que o telefone sabe fazer sozinho

Os Grandstream (GXP1610, GRP26xx, HT80x) têm os mesmos mecanismos de
provisionamento:

1. **Servidor de configuração (`Config Server Path`, P237).** Ao ligar e
   periodicamente, o telefone baixa de uma URL um arquivo chamado `cfgMAC.xml`
   (MAC = endereço MAC do aparelho, 12 hex). O arquivo é um XML com P-values,
   os mesmos que o script atual grava pela API. Suporta HTTPS, autenticação HTTP
   e variáveis `$MAC` e `$PN` na URL. Se não achar o `cfgMAC.xml`, tenta
   `cfgMODELO.xml` e `cfg.xml`.
2. **Upload de arquivo de configuração na interface web** (Maintenance >
   Upgrade and Provisioning > Config File > Upload). Aceita o mesmo XML. O campo
   `<mac>` é opcional; se presente, só aquele aparelho aceita o arquivo.
3. **GDMS / RPS (zero-touch da Grandstream).** Serviço de nuvem gratuito da
   Grandstream. Cadastra-se o aparelho pelo MAC + número de série; quando o
   telefone liga de fábrica, ele consulta o servidor de redirecionamento da
   Grandstream e é apontado para o template de configuração definido no GDMS,
   que pode conter apenas o `Config Server Path` do nosso servidor. Há API
   (`/oapi/v1.0.0/device/add` com MAC e serial) para automatizar o cadastro.
4. TR-069 e DHCP opção 66: existem, mas exigem controle do roteador ou de um
   ACS. Descartados.

Fontes: [HT80x Administration Guide](https://documentation.grandstream.com/knowledge-base/ht80x-administration-guide/), [HT80x V2 Administration Guide](https://documentation.grandstream.com/knowledge-base/ht80x-v2-administration-guide/), [GDMS API Guide](https://documentation.grandstream.com/knowledge-base/gdms-api-guide/), [VoIP.ms sobre GDMS/RPS](https://wiki.voip.ms/article/Grandstream_Device_Management_Cloud_System_(GDMS)), [GDMS](https://www.grandstream.com/products/device-management/gdms/product/gdms).

O que ainda precisa ser confirmado em bancada (ver "Validação" no fim):
os P-values exatos de "Config Upgrade Via" e intervalo de checagem no firmware
1.0.7.x do GXP1610, e se o GXP1610 valida certificado Let's Encrypt em HTTPS.

## Os três caminhos

### Caminho A — Kit pré-preparado pela ONG (recomendado para o MVP)

A ONG compra os telefones em lote. Antes de entregar, um voluntário roda um
script (variante do `configurar-telefone.sh`) que grava **uma única coisa**
no aparelho: o `Config Server Path` apontando para o servidor da rede, por
exemplo `https://prov.rede.org/boot`. Sem credencial SIP, sem ramal, nada
individual. Todos os kits recebem exatamente a mesma configuração. Dá para
fazer dez de uma vez num switch.

O site registra o MAC de cada kit preparado (o script lê o MAC do aparelho e
cadastra no banco com status "aguardando ativação"). Na caixa vai uma etiqueta
com um código de ativação curto (8 caracteres, como hoje).

Na casa da família:
1. Liga o telefone no roteador e na tomada.
2. Entra no site, cria a conta, digita o código de ativação, escolhe o apelido.
3. O site cria o ramal (ID), gera a senha SIP e marca o aparelho como "ativado".
4. O telefone, que já está perguntando ao servidor periodicamente, baixa o
   `cfgMAC.xml` com as credenciais e registra. Para não esperar o intervalo de
   checagem, a instrução é "desligue e ligue o telefone da tomada" (ele busca a
   configuração ao iniciar). O site mostra "telefone conectado" quando o
   Asterisk registrar o ramal.

Vantagens: a família não abre interface nenhuma; o site "configura o telefone"
de verdade; a ONG controla o lote (pode testar antes de enviar); funciona com
GXP1610, GRP26xx e HT80x igualmente.

Desvantagem: só funciona para aparelhos que passaram pela ONG.

### Caminho B — Arquivo de configuração (quem comprou por conta própria)

Para a família que comprou o telefone numa loja:

1. No site, depois de criar a conta e o apelido, clica em "Baixar configuração
   do telefone". O site gera um `cfgMAC.xml` (ou `config.xml` sem MAC) com as
   credenciais SIP **e** o `Config Server Path` com um token individual, para
   que atualizações futuras venham automaticamente.
2. A família abre a interface do telefone (o site explica: aperte a tecla de
   menu, vá em Status para ver o IP; abra `http://IP` no computador; senha
   `admin` de fábrica) e sobe o arquivo em Upload Configuration. O telefone
   reinicia configurado.

É o caminho 100% aberto, sem depender de ninguém. A fricção é abrir a
interface do telefone uma vez. Uma variante com menos passos é digitar só o
`Config Server Path` (uma URL com token) em vez de subir arquivo; o resultado é
o mesmo. O arquivo é preferível porque não depende de digitar URL sem erro.

### Caminho C — Zero-touch via GDMS (a experiência "apertar um botão")

Para a família que comprou por conta própria e não quer abrir interface:

1. No site, digita o MAC e o número de série (estão na etiqueta embaixo do
   telefone).
2. O site chama a API do GDMS (`device/add`) na conta da ONG e associa o
   aparelho ao template da rede, cujo único conteúdo é o `Config Server Path`
   com o token da família.
3. A família liga o telefone. Ele consulta a Grandstream, é redirecionado para
   o nosso servidor, baixa o `cfgMAC.xml` e registra.

É a experiência do Tin Can com hardware genérico. Ressalvas:

- Depende de um serviço de nuvem da Grandstream (gratuito, mas de terceiro).
  Se sumir, cai-se nos caminhos A e B; nada se perde porque, depois do primeiro
  boot, o telefone só fala com o nosso servidor.
- O aparelho precisa estar em estado de fábrica e não ter sido reivindicado
  por um revendedor no GDMS (acontece com importação paralela). Nesse caso,
  cai no caminho B.
- A API documentada cobre adicionar aparelho; a associação ao template pode
  exigir um passo no painel do GDMS (um clique por lote). Confirmar na
  referência em `doc.grandstream.dev`.
- Funciona melhor nos GRP26xx, desenhados para zero-touch. No GXP1610 (fora de
  linha) precisa ser testado.

### Recomendação

| Fase | Caminho |
|------|---------|
| MVP / piloto | C (zero-touch), com GRP2601 |
| v1 | C + B (B só para conflito de revendedor ou família com alguém técnico) |
| descartado | A (kits): exige trabalho da ONG em cada aparelho |

Em qualquer caminho, **o servidor de provisionamento é o mesmo**. Só muda como
o telefone descobre o endereço dele pela primeira vez.

## O servidor de provisionamento

Um endpoint no portal (Flask, mesmo processo), que serve o XML:

```
GET https://prov.rede.org/boot/cfg<MAC>.xml          (kits: sem token na URL)
GET https://prov.rede.org/p/<token>/cfg<MAC>.xml     (B e C: token individual)
```

Regras:

- **Caminho `/boot`**: o aparelho só é reconhecido se o MAC estiver na lista
  de kits preparados pela ONG. Se o kit ainda não foi ativado, responde um XML
  neutro (só o `Config Server Path` de novo, sem SIP). Depois da ativação,
  responde o XML completo. Um MAC desconhecido recebe 404.
- **Caminho `/p/<token>`**: token de 32+ caracteres, gerado no cadastro, único
  por aparelho. O MAC da URL tem que bater com o MAC cadastrado para aquele
  token (no caminho B o MAC é capturado no primeiro download; no C é digitado).
- **HTTPS obrigatório**, com certificado Let's Encrypt. Validar em bancada se
  o firmware do GXP1610 confia na cadeia da Let's Encrypt; se não confiar, usar
  HTTP com token longo na URL e senha SIP rotacionável (o risco é alguém na
  rede local da família ler a senha SIP, que só serve para registrar aquele
  ramal, que já é dele).
- A senha SIP nunca aparece no site. Só vai dentro do XML.
- Toda requisição é registrada (MAC, IP, user-agent, horário). É isso que
  alimenta o "seu telefone buscou a configuração às 14:32" no portal.
- "Reconfigurar telefone" no portal gera senha SIP nova e um XML novo; o
  telefone pega na próxima checagem ou ao religar.
- O XML tem versão (`<config version="N">`). O telefone só reaplica quando muda.

### Conteúdo do XML

Os mesmos P-values que o `configurar-telefone.sh` grava hoje no GXP1610
(trecho `[3/7]`), mais o que trava o telefone para uso por criança:

| Grupo | P-values | Observação |
|---|---|---|
| Conta SIP | P271=1, P47=servidor, P35/P36=ID, P34=senha, P3=apelido, P31=1, P32=2, P81=1 | iguais ao script atual |
| Rede/NAT | P52=2 (keep-alive), P130=1 (TCP) | TCP por causa do SIP ALG dos roteadores (lição 1 do projeto) |
| Áudio | P57=9 (G.722), P58=0 (PCMU), P59=8 (PCMA) | iguais |
| Discagem | P72=1 (# envia) | igual |
| Provisionamento | P237=URL do servidor, "Config Upgrade Via"=HTTPS, "Automatic Upgrade"=sim, intervalo (ex.: 1440 min) | P-values exatos a confirmar no Admin Guide do GXP16xx |
| Travas | desabilitar acesso web nível usuário, trocar senha admin por senha por aparelho, travar menu de configuração do teclado | P-values a levantar no Admin Guide; sem isso a criança pode mexer no menu |
| Firmware | não apontar para servidor de firmware (GXP1610 não tem mais atualização); GRP26xx: apontar para espelho próprio | evita surpresa de firmware novo mudando comportamento |

O módulo `prototipo/provisionamento/grandstream_xml.py` gera esse XML a
partir dos dados do ramal. Formato (confirmado nos guias da Grandstream):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gs_provision version="1">
  <mac>000B82AABBCC</mac>
  <config version="1">
    <P271>1</P271>
    <P47>sip.rede.org</P47>
    <P35>345678</P35>
    ...
  </config>
</gs_provision>
```

## Script de preparação de kits (caminho A)

Derivado do `configurar-telefone.sh`, mas muito mais simples: detecta o
aparelho (já existe), faz login (já existe), grava só P237 + "Config Upgrade
Via" + senha admin nova, reinicia, e cadastra o MAC no portal via API
administrativa com o código de ativação impresso. Como não há dado individual,
dá para rodar em lote: o script varre uma faixa de IPs e prepara todos os
Grandstream que encontrar. Um voluntário prepara 20 kits em meia hora.

## Validação em bancada (antes de escrever o portal)

Meio dia com um GXP1610 e um GRP2601 (se der para comprar um):

1. Gerar `cfgMAC.xml` com o protótipo e servir num diretório HTTPS qualquer
   (pode ser no próprio VPS atual, nginx `location /prov/`).
2. Apontar o `Config Server Path` do telefone na mão, reiniciar, ver nos logs
   do nginx a requisição e no Asterisk o registro.
3. Testar: HTTPS com Let's Encrypt funciona? `$MAC` na URL funciona? Qual o
   intervalo mínimo de checagem? A tecla de menu fica travada com os P-values
   de trava? O XML sem `<mac>` é aceito no upload manual?
4. Criar conta no GDMS, aplicar para API, cadastrar o GRP2601 e ver se o
   redirecionamento acontece de fábrica.

Resultado esperado: uma tabela de P-values confirmados por modelo, que entra
no `grandstream_xml.py` e fecha a maior incerteza do projeto.
