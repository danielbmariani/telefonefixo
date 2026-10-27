# 05 — Segurança, privacidade e aspectos legais

Abrir o cadastro muda o perfil de risco: hoje todo mundo na rede é conhecido do
Daniel. Numa rede aberta, o desenho tem que garantir sozinho que um estranho
nunca consiga falar com uma criança. A boa notícia é que a regra central já
existe e é forte: **sem autorização das duas famílias, a chamada nem toca**.

## Modelo de segurança

### O que um estranho consegue fazer

- Criar uma conta (com e-mail verificado) e um ID.
- Mandar pedido de amizade para um ID que ele conheça. Só isso. O pedido
  mostra apenas o apelido dele para a família do outro lado, que pode recusar
  ou bloquear.

### O que um estranho não consegue fazer

- Descobrir que uma criança existe: não há lista, não há busca por apelido, os
  IDs são aleatórios em um espaço de 600 mil, e um ID que existe sem amizade dá
  a mesma mensagem de voz que um ID que não existe.
- Ligar, ouvir, deixar recado ou saber se a criança está em casa.
- Ver apelido de ninguém sem ter mandado pedido para o ID certo.
- Mandar pedidos em massa: limite por conta e por dia; recusas repetidas viram
  bloqueio silencioso; contas com padrão de varredura são suspensas e revisadas.

### Controles adicionais

- **Denúncia e bloqueio** em cada contato e em cada chamada do histórico. A
  denúncia vai para a fila da ONG com o contexto (IDs, horários, apelidos).
- **Bloqueio é unilateral e definitivo** até a família desbloquear; o outro
  lado não é avisado.
- **Sem gravação de áudio.** Nunca. Só metadados (quem, quando, duração).
- **Sem caixa postal no MVP.** Caixa postal é áudio gravado de criança
  armazenado em servidor; tem implicações de privacidade e de moderação. Se
  entrar depois, só entre amigos aceitos e com retenção curta.
- **Chamada em grupo** continua exigindo amizade com todos os participantes
  (já é assim).
- **Conta de adulto suspeita**: o cadastro é sempre do responsável; não há
  conta de criança. Isso é o que a LGPD e o ECA Digital pedem, e também o que
  impede o uso da rede por adultos para falar com crianças.

## Segurança técnica

- SIP: senha forte por ramal (gerada, nunca exibida), transporte TCP; avaliar
  TLS (porta 5061, certificado Let's Encrypt) e SRTP; o GXP1610 suporta ambos,
  mas precisa de teste de confiança no certificado. `fail2ban` nos logs do
  Asterisk e do nginx. Rate limit de REGISTER por IP.
- Provisionamento: HTTPS, token por aparelho, MAC vinculado, log de todo
  acesso, XML nunca listável, rotação de senha SIP pelo portal.
- Portal: o que já existe (PBKDF2, CSRF, cookies HttpOnly/SameSite, rate limit
  de login) mais 2FA para contas da ONG, cabeçalhos de segurança no nginx,
  dependências atualizadas, backup cifrado.
- Telefone: senha admin individual por aparelho (vai no XML), acesso web do
  nível usuário desabilitado, menu de configuração travado.
- Infra: atualização automática de segurança no Ubuntu, SSH só por chave,
  firewall mínimo (o atual), Postgres só em localhost.
- Revisão de segurança externa (pode ser voluntária) antes de abrir o cadastro.

## Dados pessoais

Princípio: guardar o mínimo que faz o serviço funcionar.

| Dado | De quem | Para quê | Retenção |
|---|---|---|---|
| E-mail, senha (hash), nome | responsável | login, avisos | enquanto a conta existir |
| Apelido, ID | criança | identificação na rede | enquanto a conta existir |
| MAC, serial, modelo, IP de provisionamento | aparelho | provisionamento e diagnóstico | enquanto o aparelho estiver vinculado |
| Amizades e pedidos | família | autorização de chamadas | enquanto a conta existir |
| Horários | família | regras | enquanto a conta existir |
| Registro de chamadas (IDs, horário, duração, motivo de bloqueio) | criança | histórico para os pais, moderação | 90 dias, depois agregado sem IDs |
| Logs de servidor (IP, user-agent) | todos | segurança | 30 dias |

Não se coleta: nome real da criança (o apelido não deve ser o nome completo;
o site orienta), idade exata (só a faixa, se a ONG quiser para estatística),
escola, endereço, áudio.

Direitos: exportar tudo em JSON e excluir a conta (apaga tudo, inclusive o
ramal no Asterisk; já existe) direto no portal, sem pedir à ONG.

## LGPD

- **Base legal**: dados do responsável, execução de contrato (art. 7º, V).
  Dados da criança, consentimento específico e em destaque de pelo menos um
  dos pais ou responsável (art. 14, §1º), colhido numa tela própria, separado
  dos termos de uso. O Enunciado CD/ANPD nº 1/2023 admite outras bases para
  dados de crianças desde que prevaleça o melhor interesse; mesmo assim, o
  consentimento em destaque é o caminho mais seguro e simples aqui, porque o
  responsável está no cadastro de qualquer jeito.
- **Finalidade e minimização** (art. 6º): tabela acima; nada de uso secundário.
- **Encarregado (DPO)**: a ONG designa uma pessoa e publica o contato.
- **Relatório de impacto** (RIPD): recomendável, pelo público (crianças), mesmo
  que o volume seja pequeno. Pode ser curto.
- **Incidentes**: plano de resposta e comunicação à ANPD e aos titulares.
- **Operadores**: Oracle Cloud (infra), provedor de e-mail (SMTP), Grandstream
  (GDMS, só se o caminho C for usado, e só MAC/serial). Listar na política.

Fontes: [Felsberg sobre o Enunciado 1/2023](https://www.felsberg.com.br/importante-anpd-publica-enunciado-sobre-o-tratamento-de-dados-pessoais-de-criancas-e-adolescentes/), [Confidata sobre dados de crianças](https://confidata.com.br/blog/dados-criancas-adolescentes-lgpd).

## ECA Digital (Lei 15.211/2025)

Em vigor desde 17 de março de 2026. Alcança produtos e serviços digitais
"direcionados ou de acesso provável por crianças e adolescentes", o que inclui
esta rede. Pontos que importam e como o desenho responde:

| Exigência | Como a rede atende |
|---|---|
| Conta de criança vinculada ao responsável, com supervisão | Não existe conta de criança; a conta é do responsável, que controla tudo |
| Verificação de idade proporcional, sem autodeclaração simples | Quem cria conta é adulto (e-mail, aceite, pagamento do aparelho); a criança não interage com o site. Avaliar com advogado se é suficiente ou se cabe uma verificação do responsável |
| Configuração mais protetiva por padrão | Conta nova não fala com ninguém; nada é público |
| Minimização e proibição de perfilamento/publicidade | Sem anúncios, sem perfil, tabela de dados acima |
| Canal de denúncia e resposta | Botão de denúncia no portal + fila da ONG + prazos |
| Prevenção de riscos desde a concepção | Este documento; revisão externa antes de abrir |

Fontes: [Demarest](https://www.demarest.com.br/eca-digital-entrada-em-vigor-em-17-de-marco-de-2026/), [Olhar Digital](https://olhardigital.com.br/2026/03/16/internet-e-redes-sociais/eca-digital-comeca-a-valer-na-terca-feira-17-saiba-o-que-muda-nas-redes/), [Confidata](https://confidata.com.br/blog/eca-digital-o-que-muda-empresas). A regulamentação da ANPD ainda estava sendo publicada em fases ao longo de 2026; a ONG precisa acompanhar.

**Recomendação**: uma revisão com advogado de proteção de dados antes do
piloto. A ONG provavelmente já tem acesso a isso. O custo de fazer certo desde
o começo é baixo; o de corrigir depois, alto.

## Anatel

VoIP que não se interliga com a rede telefônica pública é tratado como
**serviço de valor adicionado** (art. 61 da Lei Geral de Telecomunicações), não
como serviço de telecomunicações, e não exige outorga. É a situação da rede:
chamadas só entre ramais do próprio servidor e para o app SIP da família.

Isso impõe uma restrição de produto consciente: **não oferecer ligação para
celular ou fixo comum** (o "Party Line" do Tin Can). No dia em que a rede
terminar chamadas na rede pública, muda de regime e passa a precisar de
operadora licenciada no meio. Não vale a pena.

Os telefones Grandstream vendidos no Brasil são homologados na Anatel (o
GXP1610 tem código de homologação nos anúncios), o que é exigido para
equipamento de telecomunicação, mesmo em SVA.

Fontes: [Migalhas, regulação de VoIP](https://www.migalhas.com.br/depeso/16467/regulacao-de-voip-no-brasil), [Migalhas, VoIP como SVA](https://www.migalhas.com.br/quentes/144299/nao-ha-incidencia-de-icms-e-iss-em-voip-por-ser-servico-de-valor-adicionado). As fontes são antigas; confirmar o entendimento atual com o advogado na mesma revisão da LGPD.

## Documentos a produzir

1. Termos de uso (curtos, em linguagem simples).
2. Política de privacidade (tabela de dados acima em prosa).
3. Tela de consentimento para dados da criança.
4. Política de moderação e denúncia (o que acontece, em quanto tempo).
5. Plano de resposta a incidentes (uma página).
6. RIPD (relatório de impacto), versão curta.
