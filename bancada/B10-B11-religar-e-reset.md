# B10 / B11 — Religar e reset de fábrica mantendo no GDMS (2026-10-26)

Aparelho: GRP2601 nº 2, MAC EC74D7XXXXXB (ID 4XX444), firmware 1.0.7.11, já com as travas
(P1357=3 menu travado, P22373=1 reset só com senha, P1650=0 web só HTTPS).

## B10 — desligar da tomada e religar

Daniel desligou e religou: o telefone voltou sozinho e registrou (relato + ps_contacts). Sem nova
busca de configuração (o P193 é diário), o que é o esperado.

## B11 — reset de fábrica

1. Pela API do GDMS (`task/add`, taskType 2, execType 1): `retCode 0`, taskId 17968493, mas o
   aparelho **não reagiu** em 6 minutos; `task/list` mostra `status: 7`, código que a referência da
   API não documenta. Hipóteses: tarefa não suportada no GRP260x por API, ou bloqueada pelo P22373.
   Não contar com reset remoto por API.
2. Pela **web do aparelho** (https://192.168.1.23, admin + senha individual mostrada pelo site em
   "Ver senha admin"): Maintenance > Upgrade and Provisioning > Factory Reset. Funcionou:

| hora | evento |
|---|---|
| 13:55 | família consultou a senha admin no site e fez o reset pela web |
| 13:57:00 | GDMS: alerta factory reset (telefone `ativo`, config de 13:26) → **caso `reset_de_fabrica` aberto, corretamente** |
| 13:57:17 | telefone buscou `cfg<mac>.xml` de novo no portal (`config_reentregue`) |
| 13:58:00 | GDMS: alerta reboot |
| ~13:58 | REGISTER novo no Asterisk (porta de origem nova), ID 4XX444 de volta no visor |

Conclusão: com o aparelho mantido na organização do GDMS, um reset de fábrica **volta sozinho em
cerca de 2 minutos**, sem cadastro novo e sem toque no menu. O caso aberto para a ONG é o
comportamento desejado (um reset fora da bancada merece um olhar). Fecha a pergunta "reativar":
enquanto o MAC estiver na org, não há nada a fazer.

Pendentes: B12 (remover do GDMS + reset: nada deve chegar), B13, B14, B18b (certificado inválido),
B19 (remover do GDMS depois de provisionado: continua funcionando?).
