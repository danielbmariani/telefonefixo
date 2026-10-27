# 04 — Fluxo da família

Jornada completa, do zero até a primeira ligação, nos dois casos: kit da ONG e
telefone comprado por conta própria. A meta é 15 minutos sem conhecimento
técnico.

## Caso 1: kit da ONG (caminho A)

**Recebe a caixa.** Dentro: telefone GXP1610, cabo de rede, fonte, um cartão com
o código de ativação (ex.: `G2GQ05LF`) e três instruções:

1. Ligue o telefone no roteador (cabo de rede) e na tomada.
2. Entre em `rede.org/ativar` e digite o código do cartão.
3. Siga o site.

**No site (`/ativar`):**

1. Código de ativação, e-mail, senha. Recebe código de 6 dígitos por e-mail e
   confirma (igual ao fluxo atual).
2. Aceite dos termos e da política de privacidade, com o consentimento para
   dados da criança em destaque e separado (LGPD art. 14).
3. Apelido da criança. O site valida (único, sem sobrenome, sem números que
   pareçam data) e mostra o ID gerado em destaque: **34 56 78**. Botão
   "imprimir cartão para a criança" (apelido, ID, como ligar, hora certa 100#).
4. Tela "Conectando seu telefone": o site fica esperando o aparelho buscar a
   configuração e registrar. Mostra os passos com check: "telefone buscou a
   configuração" → "telefone registrado". Se passar 2 minutos sem o primeiro
   check: "desligue e ligue o telefone da tomada". Se passar 5: diagnóstico.
5. "Pronto. Tire o fone do gancho e disque 100# para ouvir a hora."

**Primeiro amigo:**

6. Aba Contatos > "Adicionar amigo" > digita o ID do amigo (que a outra
   criança passou na escola). O site mostra o apelido para confirmar e envia
   o pedido. A outra família recebe e-mail e vê o pedido no portal; aceita.
   Os dois telefones podem se ligar. Status verde nas duas telas.

**Horários** (opcional): aba Horários, igual à atual (sem horário = liberado).

## Caso 2: telefone comprado por conta própria (caminhos B e C)

**No site (`/cadastrar`):**

1. E-mail, senha, verificação por e-mail, termos. Apelido e ID, como acima.
2. Tela "Conectar seu telefone", com duas opções:

   **Opção fácil (C, quando disponível):** "Digite o MAC e o número de série
   que estão na etiqueta embaixo do telefone". O site valida o formato e
   cadastra no GDMS. "Agora ligue o telefone no roteador e na tomada. Ele vai
   se configurar sozinho em até 3 minutos." Mesma tela de espera do caso 1.

   **Opção manual (B):** "Baixar arquivo de configuração" e um passo a passo
   com fotos: ligar o telefone, apertar a tecla de menu, ler o IP em Status,
   abrir `http://IP` no computador do mesmo Wi-Fi, usuário `admin`, senha
   `admin` (de fábrica), menu Maintenance > Upgrade and Provisioning > Upload
   Configuration, escolher o arquivo, aguardar reiniciar. Mesma tela de
   espera. O arquivo contém a senha nova de admin, então o passo a passo avisa
   que a senha muda e onde vê-la no portal.

3. Dali em diante, igual ao caso 1.

## O dia a dia da criança

- Tirar do gancho, discar o ID do amigo + `#`. O visor mostra o número.
- Quando recebe ligação, o visor mostra o apelido do amigo.
- Mensagens de voz em português: fora do horário (meu ou do amigo), não está
  na lista de amigos, ocupado, não atende, número inválido, chamada cheia.
- `0` + ID + `#`: chamada aberta; outros amigos em comum podem entrar (até 5).
- `9` + meu ID + `#`: celular 1 da família. `8` + meu ID: celular 2.
- `100#`: hora certa.

Nada disso muda em relação ao projeto atual, exceto o tamanho do número.

## O dia a dia dos pais

- Pedidos de amizade chegam por e-mail e aparecem no portal (e por notificação
  se instalarem a PWA).
- Histórico: quem ligou para quem, quando, quanto tempo, e bloqueios com o
  motivo (fora do horário, sem amizade).
- Horários por dia da semana.
- Telefone: estado (registrado/não), "reconfigurar" (gera credencial nova),
  "baixar configuração" de novo, trocar o telefone (novo MAC, mesmo ID).
- Família: celulares via Groundwire (igual ao atual).
- Conta: excluir conta (apaga tudo e remove o ramal; já existe), exportar dados.

## O dia a dia da ONG

- Painel: kits preparados / ativados / nunca conectados; contas criadas por
  semana; telefones registrados agora; chamadas por dia; pedidos de amizade.
- Fila de denúncias e pedidos de suporte (pode ser e-mail no início).
- Preparar lote de kits: script em lote, imprimir cartões de ativação.
