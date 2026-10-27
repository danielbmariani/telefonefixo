# B08 / B09 / B18 — primeiro boot, registro, HTTPS (2026-10-26)

Aparelho: GRP2601, MAC EC74D7XXXXXA, S/N 35103ZXXXXA, firmware 1.0.7.11. Rede doméstica do Daniel
(IP privado 192.168.1.32, público 191.32.207.123), cabo no roteador, sem tocar no teclado.

Linha do tempo (horário de Brasília):

| hora | evento | fonte |
|---|---|---|
| 11:58:46 | família informou S/N e MAC | portal |
| 11:58:48 | `device/add` ok | gdms_log |
| 11:58:49 | `device/config/xml` ok (aparelho desligado) | gdms_log |
| ~12:22 | família ligou cabo de rede, fone e energia | relato |
| 12:23:00 | GDMS: alerta factory reset (primeiro contato) | webhook |
| 12:23:43 | **telefone buscou `cfg<mac>.xml` em HTTPS no portal** (UA `Grandstream Model HW GRP2601 SW 1.0.7.11 DevId ec74d7xxxxxa`) → `config_entregue` | prov_log / nginx |
| 12:23:46 | família clicou "Já liguei" | portal |
| 12:24:00 | GDMS: online + alerta reboot | webhook |
| 12:24:04 | **REGISTER no Asterisk** (TCP, contato `sip:7XX534@191.32.207.123:40134;transport=TCP`, UA `Grandstream GRP2601 1.0.7.11`) → `registrado` | ps_contacts / observador |

B08 (boot de fábrica): a requisição chega; cerca de 1,5 min depois de ligar; user-agent acima.
B18 (HTTPS): certificado Let's Encrypt do portal aceito pelo GRP2601 de fábrica (firmware 1.0.7.11),
sem instalar CA. O teste do certificado inválido (deve recusar) fica pendente.
B09 (aplicou): registrou no Asterisk 20 segundos depois do reboot; visor com hora certa. Falta
conferir no aparelho: visor mostra apelido/ID, menu travado, P237 gravado (ler da web do aparelho).

Pendentes seguintes: B10 (religar: rebusca? P193), B11 (reset de fábrica mantendo no GDMS),
B12, B13, B14, B15 (segundo aparelho), B19.
