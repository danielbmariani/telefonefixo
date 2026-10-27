# B06 — O que a API pública do GDMS cobre (referência completa lida em 2026-10-23)

Fonte: `api_data.js` do site `doc.grandstream.dev/GDMS-API` (ver `referencia-api/`). Esta
leitura substitui a de mais cedo no mesmo dia, feita por OCR de três páginas, que não mostrava
os endpoints abaixo marcados com (!).

## Cobertura, por grupo

| Grupo | Endpoints | Serve para |
|---|---|---|
| Token | `oauth/token` (password e refresh) | E4 |
| Organization / Site | `org/list`; `site/list`, `site/get`, `site/add`, `site/edit`, `site/delete` | configuração |
| Device | `device/list`, `device/add`, `device/edit`, `device/delete`, `device/detail` (só online) | E4, reconciliação |
| Device (!) | **`device/config/xml`**: multipart `xml` + `mac` + `orgId` + `applyConfig` | **E5 sem operador** |
| Device (!) | `device/site/config/xml`: XML para todos os aparelhos do site; `applyAddDevice=true` aplica aos adicionados depois | travas/parâmetros comuns, uma vez |
| Device (!) | `device/account/configuration` (atribui conta SIP cadastrada no GDMS a um índice do aparelho), `device/account/status` (`accountStatus` Up/Disabled por conta), `device/account/info` | diagnóstico |
| SIP Server / SIP Account | CRUD completo (`sip/server/*`, `sip/account/*`, v1.1.0 aceita lista de servidores e `mac`) | não usado: a conta vai no XML |
| Task | `task/add` (1 reboot, 2 reset de fábrica, 3 firmware), `task/list`, `task/delete` | suporte |
| Push subscription (!) | `callback/set_url`, `subscribe/save`, `subscribe/info`, `subscribe/delete`, `subscribe/available_options` | **webhook**: deviceStatus (0 offline, 1 online, -1 anormal), accountStatus (Up/Disabled/exception), alertas 0 falha de registro, 2 reset de fábrica, 5 reboot, 7 tarefa falhou, 9 offline |
| Template Management (!) | `template/modelTemplate/list`, `template/group/list`, `template/config/download`, `template/push/config` {macs, id, templateType 2=modelo} | empurrar o template por modelo a MACs específicos; criar o template continua sendo pela interface |
| Channel Management | `assign`, `config`, `recycle`, `remand`, `device/list`, `sub/list` | revendedores (não usamos) |
| Error codes | tabela única | `gdms_client.ERROS_DEVICE_ADD` e afins |

Não existe: RPS (só na interface); assinatura/autenticação dos callbacks (a URL do webhook leva
um segredo longo).

## Assinatura para envio de arquivo (Signature Method, item 4)

Campos do formulário e da query entram na base como `chave=valor`; arquivos entram como
`campo=md5(conteúdo)` em minúsculas; tudo em ordem alfabética entre `&`, e `signature` vai na
query junto com `access_token` e `timestamp`. O exemplo do guia:

```
&access_token=...&cfg_file=md5(file)&client_id=...&client_secret=...&is_save=1&name=aaaaa&timestamp=...&
```

Implementado em `portal/rede/gdms_client.py` (`montar_base_formulario`, `post_form`,
`configurar_xml`). Teste unitário reproduz o exemplo do guia. **A confirmar na bancada (B06b)**:
o GDMS aceita `multipart/form-data` (como no capture do `device/site/config/xml` da referência) e
entrega o XML a um aparelho que está offline quando ele conecta pela primeira vez.

## Decisão para o E5

1. `device/add` (E4) e, na sequência, `device/config/xml` com o XML "ponteiro": `P237` =
   `https://<prov>/p/<token>/`, intervalo de recheck e travas. A conta SIP não passa pelo GDMS;
   o aparelho a busca no nosso servidor (E7), que é onde fica a prova de entrega (`prov_log`).
   Se B09 mostrar que o aparelho não rebusca o P237 logo após aplicar o XML do GDMS, muda-se
   `REDE_GDMS_XML_CONTEUDO=completo` (conta SIP dentro do XML do GDMS).
2. Webhook: `flask gdms-eventos` registra `SITE_URL/gdms/eventos/<segredo>` e assina
   deviceStatus/accountStatus/alertas da organização. Os eventos viram `gdms_log` + auditoria
   (`gdms_aparelho_online`, `gdms_conta_up`, `gdms_alerta_reset_de_fabrica` → caso). Não mudam
   estado: as provas continuam sendo a requisição em E7 e o registro em E8.
3. Template por modelo (GRP2601) fica como reserva: o `device/site/config/xml` com
   `applyAddDevice=true` faz o mesmo papel por API, sem interface. Avaliar na bancada se vale
   usar para as travas (B04 renomeado).
4. Se `device/config/xml` falhar `GDMS_MAX_TENTATIVAS` vezes, o portal abre a tarefa
   `enviar_config_gdms` para o operador (XML impresso por `flask gdms-xml <telefone_id>`).

## Códigos de erro relevantes (tabela oficial)

| Código | Texto | Onde |
|---|---|---|
| 30007 | device mac exists | device/add (idempotente) |
| 30011 | device exists another company | device/add → conflito |
| 30010 / 30004 / 30003 | device sn Error / Pattern Error / is Empty | device/add → dados inválidos |
| 30012 / 30068 | device type not support / model not supported | device/add (GXP1610) |
| 50007 | invalid mac | device/add, config/xml |
| 30014 | device mac not exists | config/xml (aparelho não está na org) |
| 30050 | device id not current org | config/xml |
| 80002 | xml config format error | config/xml |
| 32008 / 50023 | file not found / upload limit | config/xml |
| 30015 / 30020 | device not online / offline | device/detail, tarefas |
| 26022 / 26023 / 26024 | callback url error / connect refused / timeout | callback/set_url |
| 60002 / 60012..60015 / 70001 | template inexistente, tipo não suportado, id/tipo/macs vazios, grupo inexistente | template/push/config |
| 40000..40003 | signature/timestamp ausentes ou inválidos | todos |

## Como regenerar o `.txt` a partir do `api_data.js`

```python
import json, re, html
src = open('api_data.js', encoding='utf-8').read()
api = json.loads(re.search(r'define\(\s*(\{.*\})\s*\);?\s*$', src, re.S).group(1))['api']
# cada item: group, title, version, type, url, parameter/success/error -> fields{grupo: [campos]}, examples[]
```

## Estado em 2026-10-23

- HT802V2 (EC:74:D7:XX:XX:XX) foi adicionado por engano à org <org_id> e **removido pela API**
  (`device/delete`, success 1). A org está vazia.
- Template por modelo "GRP2601 bancada" criado na interface com provisionamento automático =
  Nenhum (não se aplica a aparelho algum). Serve para ler os P-values da aba Maintenance.
- Webhook ainda não registrado (precisa do portal no ar com HTTPS).
