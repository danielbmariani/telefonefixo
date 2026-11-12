# 08 — Decisões em aberto

O que precisa ser decidido (com a ONG, ou pelo Daniel) antes de começar a
fase 1. Para cada uma há uma recomendação; basta confirmar ou mudar.

## Produto

1. **Nome e domínio.** Precisa ser dizível por criança de 7 anos e fácil de
   escrever para os pais. Ideias: "Fio", "Telefone dos Amigos", "Ramal",
   "Linha Direta", "Alô". Recomendação: nome curto + `.org.br`.
2. **Hardware.** Decidido em 23/10: GRP2601 como referência (o GXP1610 não é
   suportado pelo GDMS). Falta decidir se o GRP2602W (Wi-Fi) entra na lista
   recomendada depois da bancada B16.
3. **Tamanho do ID.** 6 dígitos aleatórios começando por 2 a 7. Alternativa:
   5 dígitos (60 mil IDs). Recomendação: 6.
4. **Caixa postal.** Fora do MVP. Decidir se entra na fase 3 e com que regras.
5. **Chamada em grupo.** O "0 + ID" do v1 não serve para a rede nova; proposta completa (grupo com nome montado pelos pais, `0` + dígito, toca em todos, voz anuncia quem entra e sai) em `docs/16-chamada-em-grupo.md`. Decisões pendentes no fim do doc 16.
6. **Celular da família.** A numeração já prevê 9+ID e 8+ID (dois ramais da
   família) e o dialplan tem o gancho (`BLOCK_PARENT`). Três caminhos, avaliados
   em 26/10/2026:
   a. *App pronto com push*: Groundwire (pago, ~R$ 50 uma vez) toca com o app
      fechado porque usa o serviço de push da Acrobits. É o que a rede atual usa.
      Linphone é grátis, mas push só com o servidor deles (Flexisip); sem push, o
      celular só toca com o app aberto, o que não serve.
   b. *App próprio*: possível, mas o difícil não é a ligação, é fazer o celular
      tocar com o app fechado: push da Apple (PushKit) e do Google, um serviço
      nosso que avise o app antes de o Asterisk discar, conta de desenvolvedor
      Apple (US$ 99/ano), lojas, e manutenção a cada versão de iOS e Android.
      É o item de maior manutenção de todo o projeto para uma ONG com um
      desenvolvedor. Só se a rede crescer e houver alguém para cuidar.
   c. *Sem app*: a criança disca 9+ID e o Asterisk liga para o celular real do
      responsável por um tronco SIP de operadora, só para os números cadastrados
      na conta (e o responsável liga para a criança se o identificador bater).
      Custo por minuto (centavos), toca em qualquer celular, sem instalar nada.
      É o "Party Line" da Tin Can, que 85% dos clientes dela pagam. Abre a rede
      para a telefonia comum, então precisa de lista fechada e limites.
   Decisão do Daniel (26/10/2026): (a) **descartado** ("tem que funcionar para
   absolutamente todo mundo"; app de terceiros só complica). Ele tem conta de
   desenvolvedor Apple, o que tira um custo de (b), mas não a manutenção.
   Caminho escolhido para estudar: (c).

   Como o dinheiro pode circular em (c), pesquisa de 26/10:
   - *Conta própria de cada família na operadora, recarga por Pix direto nela,
     crédito fica com a família, nada passa pela ONG.* É o mais limpo (a ONG
     não revende telefonia, não recebe dinheiro), mas as operadoras brasileiras
     que vendem conta SIP a pessoa física cobram mensalidade só para a conta
     existir: Voipi R$ 19,90 a 25/mês (+ R$ 0,35/min celular), RamalVirtual
     R$ 49,80/mês, BRVOZ a partir de R$ 28/mês. Para 30 min/mês, a mensalidade
     custaria 2 a 5 vezes mais que os minutos. Inviável como padrão; serve só
     como opção para quem já tem conta VoIP.
   - *Um tronco da ONG para toda a rede, só por minuto* (Diskfree ~R$ 0,20/min
     celular, Voipmundo ~R$ 0,30, Twilio ~R$ 0,35; fixo R$ 0,08 a 0,12), e o
     crédito de cada família controlado pelo portal: a família faz um Pix (QR
     gerado pelo site via Asaas/Efí/Mercado Pago, com webhook) e o Asterisk
     limita a ligação ao saldo (`Dial` com `L()`). 30 min/mês ≈ R$ 6 a 10. O
     dinheiro passa pela ONG (receita, contabilidade) e é preciso checar com
     contador/advogado se "minutos a preço de custo para associados" configura
     revenda de STFC perante a Anatel.
   - *Variante sem saldo*: contribuição anual fixa (ex.: R$ 60) que dá direito
     a X minutos/mês só para os números cadastrados da família. Mais simples de
     explicar que saldo; mesma questão jurídica.
   Bancada B23 (plano e comparação de operadoras em
   `bancada/B23-tronco-celular-dos-pais.md`): uma conta só, em nome do Daniel,
   na Nvoip (autorizada pela Anatel, plano sem mensalidade, crédito por
   minuto, tronco SIP com provisionador oficial para Asterisk; a Voipi, primeira
   escolha, não opera); reserva Telnyx (aceita pessoa física com CPF; Twilio não dá número local a
   pessoa física). Prova os dois sentidos: 9+ID toca no celular cadastrado e o
   celular cadastrado toca no telefone da criança. **Feito em 27/10: funcionou
   nos dois sentidos** (ver B23). Decisão do Daniel (27/10, tarde): **fase de
   teste paga por ele**, com teto de R$ 5 por criança por mês e disjuntor de R$ 20
   por dia para a rede (`servicos/custos.py`; tarifas estimadas R$ 0,30/min saída e
   R$ 0,05/min entrada, ajustáveis quando a Nvoip mostrar a fatura real); aviso por
   e-mail a 80% e 100%; mensagem no telefone quando acaba; aviso no site e nos
   termos (versão 2026-10-c) de que a fase pode ser encerrada e outra solução será
   buscada com as famílias. Descartado: a família pagar direto à Nvoip dentro da
   conta do Daniel (a API não cria contas nem cobra; revenda exige CNPJ e o dinheiro
   passa pelo revendedor). Alternativa documentada: conta própria da família na Nvoip
   (fricção de 15 min por família), só se alguém pedir. Confirmado com o Daniel em
   26/10: app próprio fica como segundo caminho, só se o custo por minuto
   pesar e houver quem mantenha; o tronco continua para quem não tem
   smartphone.

   **Decisão de 05/11/2026 (quem paga, em escala).** O critério do Daniel: não dar
   trabalho ao usuário; o trabalho dele não é problema. Sem CNPJ por um bom tempo.
   Orçamento do projeto: R$ 500 por mês. O pai não paga nem faz nada; quando o gasto
   chegar perto do orçamento, abrem-se doações voluntárias, sem relação com o uso.
   No código (`servicos/custos.py`): orçamento mensal da rede `REDE_TETO_REDE_MES`
   (R$ 450, os R$ 500 menos o número da operadora), teto efetivo por criança igual ao
   menor entre `REDE_TETO_CRIANCA_MES` e o orçamento dividido pelas crianças com celular
   cadastrado (a soma nunca passa do orçamento), aviso por e-mail a 80% e 100% do orçamento e
   quadro "Celulares" no painel com gasto, projeção e uso por criança.
   Continua na Nvoip por minuto; a troca de operadora fica para quando o uso crescer.
   Para os pais, a aba Celulares fala só em minutos (quanto a criança usou e quanto
   ainda pode ligar no mês); dinheiro aparece apenas no painel do operador. Os termos
   passaram à versão 2026-11-a com o mesmo ajuste (limite de minutos, sem valor em
   reais); como a versão mudou, cada família aceita os termos de novo no próximo acesso.

   Pesquisa de 05/11 que sustenta a decisão (preços vistos nos sites nesse dia):
   - *Carteira com recarga do pai*: é o caminho de mais atrito e esbarra na Anatel.
     Revender telefonia sem autorização é tratado como serviço clandestino; o caminho
     formal é contrato de marca branca com operadora STFC (VulcaNet, TIP Brasil,
     DiskFree; a Vono prevê revenda na cláusula 14 das condições gerais). Pix
     Automático (o pai autoriza uma vez) exige recebedor com CNPJ ativo há 6 meses.
   - *Canal ilimitado*: Vono, R$ 50 por canal ao mês (R$ 40 de 9 a 20 canais), aceita
     CPF, sem fidelidade. As condições gerais limitam o "ilimitado" a 5.000 minutos
     por mês (20.7), proíbem revenda e call center (20.2, 20.6) e deixam a
     interpretação com a Vono (20.5). Número fixo: R$ 32,90 por mês (por minuto) ou
     R$ 69,90 (ilimitado, 1 simultânea). Antes de contratar, perguntar por escrito se
     o uso cabe, se o tronco vem com número, se os 5.000 minutos são por canal e se
     dá para portar o número da Nvoip.
   - *Nvoip, onde já estamos*: pacotes mensais Ligar 1000 (R$ 99, 1.000 minutos
     compartilhados) e Ligar Ilimitado (R$ 99, preso a um ramal). Falta ver no painel
     se o Ligar 1000 vale para celular e para tronco SIP. A API tem consulta de saldo.
   - *WhatsApp (API de chamadas da Meta)*: pai liga grátis; criança para o pai a
     R$ 0,0556 por minuto (valor de fonte secundária); fala SIP (direto ou pela
     Telnyx). Exige conta com limite de 2.000 mensagens por dia, que vem com a
     verificação da empresa (CNPJ). Fica para quando houver CNPJ.
   - *Grandstream/GDMS*: não vende ligações; o CloudUCM é uma central, não um tronco.
   - Conta de capacidade (Erlang B, pico de 3 horas, 10% de ocupado): com 10 minutos
     por criança ao mês, 1 canal atende cerca de 60 crianças e 2 canais, 320; com
     60 minutos, 9 e 53. O uso real ainda não foi medido.
   Fontes: falevono.com.br/sip-trunk, falevono.com.br/numero-fixo-virtual,
   falevono.com.br/assets/documents/condicoes-gerais-contratacao.pdf,
   nvoip.com.br/blog/ligacoes-ilimitadas,
   developers.facebook.com/documentation/business-messaging/whatsapp/calling (pricing,
   user-call-permissions, sip) e .../whatsapp/messaging-limits,
   telnyx.com/release-notes/whatsapp-business-calling-telnyx,
   vulcanet.com.br/en/solutions/telefonia/atacado/isp, tipbrasil.com.br/tip-fixa,
   diskfree.com.br/parcerias/negocio-proprio-de-revenda-de-telefonia-voip,
   telesintese.com.br/anatel-fez-mais-de-200-fiscalizacoes-contra-provedores-sem-outorga,
   infomoney.com.br (regras de segurança do Pix Automático), woovi.com/planos-e-precos,
   twilio.com/pt-br/sip-trunking/pricing/br.

   **Pesquisa de 07/11/2026 (metas novas do Daniel: pai paga nada ou até R$ 5, ao menos 5 h por
   mês, mil crianças, projeto gasta até R$ 1.000 por mês).** Está em `docs/17-celular-a-custo-zero.md`.
   Conclusão: por minuto não fecha em nenhuma operadora; cabem no orçamento (a) retorno automático
   (toque no celular + pai retorna para o número da rede, entrada grátis na Nvoip, custo zero),
   (b) canais ilimitados da Vono (R$ 40 a 50 por canal, 5.000 min/canal, CPF, sem fidelidade) e
   (c) WhatsApp Calling por SIP (pai liga grátis; exige limite de 2.000 mensagens, CNPJ ou volume).
   Recomendação: A agora, B após medir o uso do piloto, C quando houver CNPJ. Decisão do Daniel em 07/11: A descartado (pai teria de retornar a ligação); seguir com B e depois C. **Feito em 09/11/2026 (bancada B30):** Vono contratada com 4 canais e número (11) 5444-1774, segundo tronco na central com queda para a Nvoip, saída, entrada e queda provadas com ligação real. Teto por criança subiu para 300 min de saída e 1.800 de entrada por mês (segurança, não custo). Provas B29 a B31 (B26 a B28 já eram TLS, certificado e jitterbuffer na bancada).
7. **Faixa etária.** A rede é para crianças sem celular (grosso modo 6 a 12).
   Adolescentes podem usar, mas o ECA Digital trata adolescentes diferente.
   Recomendação: não perguntar idade exata; perguntar faixa só para
   estatística da ONG, opcional.
8. **Migração da rede atual.** Opcional. Recomendação: migrar depois do
   piloto, se a rede aberta estiver estável, e desligar a antiga para não
   manter duas.

**Domínio (feito em 27/10/2026).** `telefonefixo.org`, registrado pelo Daniel na Cloudflare (US$ 11,20/ano,
renovação automática, dados do titular ocultos), DNS na própria Cloudflare sem proxy. Site em
https://telefonefixo.org com certificado Let's Encrypt; `www` redireciona. O endereço antigo
(rede-aberta-bancada.duckdns.org) redireciona para o novo, exceto `/p/` (configuração dos telefones já
provisionados, P237) e `/gdms/` (webhook), que continuam servidos nele; novos telefones recebem o endereço novo. Webhook do GDMS re-registrado.
Script: `portal/deploy/dominio.sh`. Descartados: `telefonefixo.com.br` (de terceiro desde set/2026).

## Operação

9. **Quem é o responsável técnico secundário.** Precisa existir desde a fase 1.
10. **Canal de suporte.** E-mail da ONG ou WhatsApp? Recomendação: um só
    canal, com roteiro de diagnóstico e as perguntas mais comuns no site.
11. **Kits: venda a custo, empréstimo ou doação?** Depende do modelo da ONG.
    Recomendação: a custo, com fundo para subsidiar.
12. **Quem modera** e em quanto tempo responde uma denúncia. Recomendação:
    pessoa nomeada, 48 horas úteis para primeira resposta.

## Legal

Pesquisa e situação em `docs/13-termos-e-lgpd.md` (27/10/2026): textos versão 2026-10-b, lacunas de
implementação fechadas (retenção, exportação, exclusão completa, canal de denúncias, faixa etária);
pendentes advogado, ONG como controladora, cobrança de minutos (Anatel/CDC).

13. **Revisão com advogado de proteção de dados** antes do piloto (LGPD, ECA
    Digital, entendimento atual da Anatel sobre VoIP sem interconexão).
14. **Encarregado de dados (DPO)** nomeado pela ONG.
15. **CNPJ responsável pelo serviço** (a ONG) e titular do domínio, da conta
    Oracle, do GDMS e do e-mail transacional. Hoje tudo está em nome do Daniel.

## Técnico

16. **Postgres desde o início ou SQLite no piloto?** Recomendação: Postgres
    desde o início; a troca depois custa mais do que o setup agora.
17. **TLS/SRTP no SIP já no MVP?** Recomendação: não; TCP como hoje, TLS na
    fase 3 depois de testar o certificado nos aparelhos.
18. **Caminho C (GDMS).** Decidido em 23/10: é o caminho padrão. O que a
    bancada ainda decide: variante RPS ou template, e se a associação ao RPS
    tem API (sem API, há um passo manual da ONG por aparelho, o que contraria
    a premissa de não dar trabalho à ONG e precisa ser resolvido antes do
    piloto).
19. **Repositório.** Novo repositório (`rede-aberta`) ou branch do
    `telefone-fixo`? Recomendação: repositório novo, mantendo o histórico do
    atual como ponto de partida (fork), porque o público e a ONG são outros.
20. **Licença.** MIT (como hoje) ou AGPL (obriga quem rodar uma instância
    modificada a publicar o código)? Recomendação: AGPL-3.0 para a rede
    aberta, por ser infraestrutura para crianças operada por terceiros;
    discutir com a ONG.

   **Ajuste de 07/11/2026.** O teto por linha começou em R$ 5 e, com os testes de
   uma semana, a linha de teste chegou a 80% no dia 7. Decisão do Daniel: cerca de 50
   minutos por linha neste começo, `REDE_TETO_CRIANCA_MES=15` (50 minutos ligando para o
   celular ou 300 recebendo, por mês); depois se pensa melhor. Os e-mails de 80% e 100% por linha passaram a
   falar só em minutos, com "celular" no título; dinheiro fica só nos avisos do
   orçamento da rede e no painel.

## Adoção (10/11/2026, a partir da conversa com a Rita; análise e pesquisa em `docs/18-fixo-comum-vs-rede.md`)

21. **Texto do site sem "rede fechada" nem "controle".** A primeira mãe do piloto, que gostou do
    telefone, leu a rede como cerca e tarefa a mais. Decisão do Daniel (10/11): reposicionar como "um
    telefone fixo que só toca para quem a família conhece"; a proteção é consequência. Opções de frases
    no doc 18, seção 4.1. Pendente: aplicar nas páginas inicial e "Por dentro" e nos textos legais.
22. **Números fixos de amigos e parentes cadastrados pela família.** Descartado pelo Daniel
    (10/11): a rede segue só com os celulares da própria família. Raciocínio no doc 18, 4.2.
23. **Turma com amizade automática.** Opção da turma, escolhida por quem administra; a família
    consente ao entrar vendo a lista; bloqueio sempre vence. Pendente: Daniel decidir; revisão com
    advogado (item 13) antes de virar padrão. Doc 18, 4.3.
24. **Teste da Rita com fixo comum como braço do piloto.** Perguntas combinadas para 10/12/2026 no doc
    18, 4.4. O piloto do Felipe é o outro braço.
