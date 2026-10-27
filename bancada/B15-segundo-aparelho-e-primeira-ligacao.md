# B15 — Segundo GRP2601 e primeira ligação entre os dois (2026-10-26)

Aparelho 2: GRP2601, MAC EC74D7XXXXXB, S/N 35103ZXXXXB, firmware 1.0.7.11, de fábrica. Mesma rede
doméstica do aparelho 1. Fluxo feito pelo Daniel sozinho pelo site (segunda criança na mesma conta).

| hora | evento |
|---|---|
| 13:14:02 | família informou S/N e MAC (segunda criança, ID 4XX444) |
| 13:14:05 | `device/add` ok |
| 13:14:06 | `device/config/xml` ok (aparelho desligado), já com as travas (P1357=3 etc.) |
| 13:25:42 | família clicou "Já liguei" |
| 13:26:52 | telefone buscou `cfg<mac>.xml` em HTTPS (1 min depois de ligar) |
| 13:27:00 | GDMS: factory reset + online + reboot (um só callback) |
| 13:27:44 | REGISTER no Asterisk (TCP) → `registrado` |
| 13:36:06 | pedido de amizade 4XX444 → 7XX534 pelo site; 13:36:30 aceito na outra criança |
| 13:37:23 | **ligação 7XX534 → 4XX444: ALLOWED, 15 s** (call_logs); aparelho 1 → `ativo` |

Conclusões:
- Reprodutível: segundo aparelho, mesmo caminho, sem toque no menu. Tempo total de "ligar" a
  "conectado": 2 min.
- O alerta "factory reset" do GDMS chega *depois* do telefone buscar a nossa configuração (13:26:52 →
  13:27:00), junto com online/reboot. Regra do caso `reset_de_fabrica` ajustada: só com telefone já
  conectado e configuração com mais de 15 min.
- Travas enviadas no XML ponteiro desde o cadastro (ver B04/B09): menu do teclado a confirmar no
  aparelho pelo Daniel.
- Achados de UX corrigidos no mesmo dia: ordem S/N → MAC igual à etiqueta; MAC sem dois-pontos;
  campo "Onde comprou?" removido; botão de envio com "Registrando…" (o cadastro no GDMS leva 3 a 6 s
  dentro da requisição); tela do telefone virou passo a passo com dono "Você"/"Automático" e o desenho
  dos cabos dentro do passo; O/0 e I/1 corrigidos automaticamente (MAC) ou tentados no GDMS (S/N);
  botões "Autorizar amigos" e "Cadastrar outra criança" depois da conexão; campo de ID do amigo sem
  exemplo plausível.
