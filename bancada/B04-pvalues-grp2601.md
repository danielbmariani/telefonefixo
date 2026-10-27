# B04 — P-values do GRP2601 lidos do template do GDMS (2026-10-23)

Método: template por modelo "GRP2601 bancada" (auto-provisionamento = Nenhum), marcar os campos
na aba Maintenance > Upgrade and Provisioning, Salvar, "Mudar para o editor de texto". Evidência:
`Screenshot from 2026-10-23 16-59-04.png` (fora do git).

| P | Campo | Padrão | O que o portal grava |
|---|---|---|---|
| 212 | Config Upgrade via (0 TFTP, 1 HTTP, 2 HTTPS) | 2 | 2 |
| 237 | Config Server Path | fm.grandstream.com/gs | `https://<prov>/p/<token>/` |
| 194 | Automatic Upgrade | 0 | 1 |
| 193 | Automatic Upgrade interval (min) | (não lido) | `PROV_INTERVALO_MIN` |
| 238 | Firmware Upgrade and Provisioning (0 sempre checa fw, 1 só se prefixo mudar, 2 pula fw) | 0 | 2 |
| 145 | Allow DHCP Option 43 and 66 to Override Server | 1 | 0 |
| 1414 | 3CX Auto Provision | 1 | 0 |
| 9996 | User Protection **ou** Validate Hostname in Certificate | 0 | a confirmar (B09, exportar do aparelho) |
| 22030 | o outro dos dois acima | 0 | a confirmar |

Nota: no GRP o campo "Config Upgrade via" é o P212 (não o P6767 dos HT80x). `grandstream_xml.py`
atualizado (`pvalues_provisionamento(..., modelo='grp'|'ht')`).

Outros campos vistos na tela, sem P-value ainda: Config Server Username/Password, Always
Authenticate Before Challenge, Config File Prefix/Postfix, Authenticate Conf File (P1 = senha admin no
XML, segundo o guia de segurança), XML Config File Password (P1359), Randomized Automatic Upgrade,
Firmware Upgrade Confirmation, Allow DHCP Option 120 to Override SIP Server, Additional Override
DHCP Option, Download and Process ALL Available Config Files, Disable SIP NOTIFY Authentication.
Travas de menu/teclado e acesso web ficam em outras abas (System Settings > Security); ler na bancada.

## Resolvido em 26/10/2026 com o template oficial

Fonte: `referencia-pvalues/grp260x_config_1.0.7.74.txt` (pacote "Configuration Template" da Grandstream).

| P | nome | nosso valor |
|---|---|---|
| P9996 | User Protection (0 off) | 0 |
| P22030 | Validate Hostname in Certificate (0 no) | 0 (a testar: B18b) |
| P8463 | Validate Server Certificates | padrão 0 (a testar: B18b) |
| P1357 | Configuration via Keypad Menu (0 livre, 1 básico, 2 restrito, 3 travado) | 3 |
| P22373 | Factory Reset Security Level (1 sempre pede senha) | 1 |
| P1650 | Web Access Mode (0 HTTPS, 1 HTTP, 2 desligado, 3 ambos) | 0 |
| P8469 | Enable User Web Access | 0 |
| P276 | Enable SSH (0 sim, 1 não) | 1 |
| P196 | User Password | derivada da admin |
| P2 | Admin Password | individual por aparelho |
| P1382 | Enable Keypad Locking (trava de teclas, não usamos) | padrão 0 |

Implementado em `portal/rede/grandstream_xml.py::pvalues_travas`. Enviado ao aparelho 1 por
`flask gdms-reenviar-config 3` às 12:42 (retCode 0); aparelho 2 já recebeu no cadastro.
