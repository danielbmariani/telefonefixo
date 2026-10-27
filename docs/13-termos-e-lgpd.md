# 13. Termos, privacidade e LGPD (27/10/2026)

Pesquisa feita a pedido do Daniel ("o que deve constar nos termos e se estamos de acordo com a LGPD"),
antes de convidar famílias de fora. Resultado: três textos novos (versão 2026-10-b em
`portal/rede/textos/`), cinco lacunas de implementação fechadas no mesmo dia e uma lista do que ainda
depende de advogado ou de decisão da ONG. Nada aqui substitui revisão jurídica; serve para que a revisão
comece de um texto que já reflete o que o sistema faz de verdade.

## 1. Leis que alcançam o serviço

| Norma | O que pede de nós | Situação |
|---|---|---|
| **LGPD** (Lei 13.709/2018), art. 14 | Dados de criança (menor de 12) só no melhor interesse dela; consentimento específico e em destaque de um dos pais (§1º); informar o que é coletado (§2º); não condicionar a participação a dados além do necessário (§4º); esforço razoável para verificar que quem consentiu é o responsável (§5º); linguagem simples (§6º). Enunciado CD/ANPD 1/2023: outras bases do art. 7º também valem, desde que no melhor interesse. | Tela própria de consentimento antes de cadastrar a criança, com versão e hash do texto guardados; coleta mínima (apelido + ID, sem nome, idade, escola, foto, voz); verificação do responsável por e-mail confirmado + declaração expressa. Texto refeito em linguagem simples. |
| LGPD, arts. 9º, 18, 37, 46, 48 | Transparência, direitos do titular, registro das operações, segurança, comunicação de incidente. | Política lista dados, finalidade, prazo, base legal e operadores. Direitos: exclusão e cópia pelo próprio site (novo `/meus-dados.json`), demais por e-mail em 15 dias. Auditoria somente acréscimo. |
| LGPD, art. 33 | Transferência internacional só com um dos mecanismos do artigo. | Grandstream (EUA) e Google (e-mail): enquadradas no inciso IX com o art. 7º, V (necessárias para executar o serviço), informadas na política. Oracle e Nvoip ficam no Brasil. Cloudflare só DNS e registro. Alternativa, se a ONG quiser: usar a região EU do GDMS, que continua sendo transferência internacional, então não resolve. |
| **Resolução CD/ANPD 2/2022** (agentes de pequeno porte) | Pessoa natural e associação sem fins lucrativos sem tratamento de alto risco: dispensa de encarregado formal, mas canal de comunicação com o titular obrigatório; registro simplificado; prazos em dobro. Alto risco exige um critério geral (larga escala ou afetar significativamente interesses) mais um específico (dados de crianças conta como específico). Em escala de piloto, não é alto risco; quando a rede crescer, reavaliar. | Canal: `privacidade@telefonefixo.org` (a criar, ver seção 5). Controlador nomeado na política: Daniel Mariani, pessoa física, até a ONG assumir. |
| **Resolução CD/ANPD 15/2024** (incidentes) | Comunicar à ANPD e aos titulares em 3 dias úteis a partir de saber que dados pessoais foram atingidos (em dobro para pequeno porte); complementar em 20 dias úteis; aviso público por 3 meses quando não der para avisar cada um; registrar todo incidente por 5 anos, mesmo os não comunicados. | Procedimento na seção 4. Política promete 3 dias úteis. |
| **ECA Digital** (Lei 15.211/2025, em vigor desde 17/03/2026 pela Lei 15.352/2026) | Aplica-se a serviço de TI direcionado a crianças (art. 1º, 2º, I). Deveres: melhor interesse (art. 3º), prevenção de contato com adultos não autorizados (art. 6º), configuração mais protetiva por padrão (art. 7º), informar a faixa etária indicada (art. 8º), informar pais e crianças sobre riscos (art. 16), ferramentas de supervisão parental acessíveis e padrão protetivo, incluindo "restrição à comunicação por usuários não autorizados" (art. 17, §4º, I), ferramentas para os pais gerirem conta e privacidade e "identificar os perfis de adultos" com quem a criança fala (art. 18), conta de menor de 16 vinculada à do responsável (art. 24), canal público e de fácil acesso para denúncias, não anônimo para pedidos de retirada (arts. 28 e 29), registro de casos de abuso (art. 33, §3º). Sem perfilamento nem publicidade (arts. 22 e 26). Obrigações moduladas por porte (art. 39), critérios ainda por regulamento. Multa sem faturamento: R$ 10 a R$ 1.000 por usuário cadastrado (art. 35, II). Sem isenção para sem fins lucrativos. Verificação de idade "a cada acesso" (art. 9º) é só para conteúdo impróprio, não é o nosso caso. | O desenho da rede já é o que a lei chama de padrão protetivo: ninguém de fora liga, nenhuma conta de criança, só o responsável mexe no site, horários, silenciar, histórico, celulares só da própria família. Adicionados hoje: faixa etária no rodapé e nos termos, página pública "Contato e denúncias", orientação de contar à criança que há registro. Falta: registro formal de denúncias recebidas (hoje é o e-mail; quando houver volume, uma tabela `denuncias` no painel da ONG). |
| **Marco Civil** (Lei 12.965/2014), art. 15 | Guarda de registros de acesso a aplicações por 6 meses, obrigatória para pessoa jurídica com atividade organizada, profissional e com fins econômicos. Art. 10: registros só saem por ordem judicial; dados cadastrais a autoridades com competência legal. | Não somos obrigados (sem fins econômicos), mas guardamos os registros de acesso do nginx por 6 meses por prudência (logrotate) e a política diz isso. Pedidos de autoridade: só por ordem judicial para registros de ligação. |
| **Sigilo das comunicações** (CF art. 5º, XII; Lei 9.296/1996; LGT art. 3º, V) | Registros de chamadas são dados protegidos; quebra só por ordem judicial. | Política explicita. Não há gravação de áudio. |
| **Anatel** | VoIP entre participantes é serviço de valor adicionado (SVA), fora da outorga. Com o tronco (B23), a operadora autorizada é a Nvoip; nós somos cliente dela. Se a ONG passar a cobrar minutos das famílias, verificar com advogado se configura revenda de STFC. | Termos dizem que o custo é coberto pelo projeto e que qualquer cobrança exigirá novo aceite. |
| **CDC** | Natureza sem fins lucrativos não afasta o CDC por si (STJ, REsp 2.173.952/2024: depende do objeto). Enquanto gratuito, baixo risco; com cobrança, aplica-se com mais força (informação, cancelamento, arrependimento). | Termos já têm foro do domicílio do responsável, aviso de 30 dias para encerrar, limites claros. |

## 2. Inventário de dados (o que a política promete e o código faz)

| Dado | Finalidade | Base legal | Guarda | Onde |
|---|---|---|---|---|
| Nome, e-mail, hash da senha do responsável | login, avisos | art. 7º, V | enquanto a conta existir; na exclusão viram `excluida-<id>` | `familias` |
| IP e user-agent das ações do responsável | segurança, auditoria | art. 7º, IX | IP apagado após 1 ano (`retencao.sql`); linha fica sem nome | `audit_log` |
| Apelido, ID, senha SIP da criança | identificar o telefone | art. 14, §1º | enquanto a conta existir; na exclusão apelido vira `removido-<id>`, senha invalidada | `criancas`, `ps_*` |
| MAC, S/N, modelo, IPs e horários de conexão do aparelho | configurar e diagnosticar | art. 7º, V | registros técnicos 180 dias (`prov_log`, `gdms_log`, `device_state_history`) | `telefones`, logs |
| Registro de ligações (quem, quando, duração, motivo de bloqueio) | histórico da família, segurança | art. 14, §1º + art. 7º, IX | 90 dias, depois só totais por dia (`chamadas_resumo`); apagados na exclusão | `call_logs` |
| Celulares da família (número, apelido) | 9/8+ID e entrada pelo tronco | art. 7º, V | enquanto cadastrados; apagados na exclusão | `familia_telefones` |
| Amizades, turmas, horários, silenciar | supervisão | art. 7º, V / art. 14 | enquanto a conta existir | tabelas próprias |
| Consentimentos (tipo, versão, hash, data, IP) | prova do aceite | art. 7º, VI (exercício regular de direitos) | 5 anos após exclusão | `consentimentos` |
| Registros de acesso do nginx | segurança, Marco Civil por prudência | art. 7º, II/IX | 6 meses | `/var/log/nginx` |
| Áudio das ligações | não guardado | | passa pelo Asterisk, nada em disco | |
| Cookie | sessão | necessário | sessão | navegador |

Operadores: Oracle Cloud (São Paulo, hospedagem), Grandstream GDMS (EUA: MAC, S/N, modelo, estado online), Nvoip (Juiz de Fora: números de celular e registros das ligações para celular), Google (SMTP: e-mail e texto dos avisos), Cloudflare (registro e DNS), Let's Encrypt (certificado, sem dados pessoais). Falta formalizar: contrato de operador (DPA) da Oracle e da Nvoip existe nos termos padrão deles; conferir e arquivar.

## 3. O que foi corrigido hoje (lacunas entre o texto antigo e o sistema)

1. A política antiga prometia retenção de 90/180 dias e "exportar pelo site", mas nada disso existia. Agora: `servicos/retencao.py` (chamadas → totais por dia, no job diário), `deploy/retencao.sql` + cron (tabelas somente-acréscimo, IP da auditoria após 1 ano, tokens após 30 dias), `/meus-dados.json` (cópia completa em JSON, com registro na auditoria).
2. A exclusão de conta não apagava os celulares da família nem as ligações das crianças. Agora apaga; mantém consentimentos (prova) e auditoria sem nome.
3. Não havia canal público. Agora `/contato` (denúncias identificadas, prazo de 48 h úteis, Disque 100 e 190, canal do titular) e links no rodapé.
4. Faixa etária indicada (ECA Digital, art. 8º) no rodapé e nos termos: "a partir de 6 anos, sempre com um responsável". Configurável em `REDE_FAIXA_ETARIA`.
5. Textos reescritos (sem travessões, sem placeholders) e versão subida para 2026-10-b: todas as famílias precisam aceitar de novo no próximo acesso, o que também serve de prova da mudança.

## 4. Procedimento de incidente (para colar no manual da ONG)

1. Descobriu vazamento, acesso indevido ou perda de dados: anotar data e hora em que soube. O prazo conta daí.
2. Conter (trocar senhas e chaves, bloquear conta, derrubar serviço se preciso) e preservar logs (`audit_log`, nginx, Asterisk).
3. Avaliar: quais dados, de quantas famílias e crianças, risco para elas.
4. Até 3 dias úteis (6 por ser pequeno porte, mas a política promete 3): formulário da ANPD (gov.br/anpd, "Comunicação de incidente") e e-mail às famílias afetadas; se não der para identificar todas, aviso no site por 3 meses.
5. Complementar em até 20 dias úteis. Registrar tudo em `docs/incidentes/AAAA-MM-DD.md` e guardar por 5 anos, mesmo se decidir não comunicar.

## 5. O que o Daniel precisa fazer agora

1. **Criar os dois e-mails** na Cloudflare, sem custo: no domínio `telefonefixo.org`, menu "Email", "Email Routing", "Enable", depois "Create address" para `contato` e `privacidade`, ambos encaminhando para o seu Gmail. A Cloudflare pede para adicionar registros MX e TXT; aceite o botão "Add records automatically". Os textos já citam esses endereços.
2. Ao entrar no site, aceitar os três textos novos (vai aparecer a tela de consentimento de novo).
3. Avisar a criança de que o telefone registra as ligações (está nos termos como dever da família).

## 6. O que fica para advogado ou para a ONG

1. Revisão dos três textos por advogado com prática em LGPD e infância, idealmente antes do piloto com a turma dessa mãe. Os textos estão em português simples de propósito; o advogado deve manter isso.
2. Quando a ONG assumir: trocar o controlador nos textos e no `REDE_CONTROLADOR_NOME`, nomear quem responde pelo canal, registrar operações de tratamento (formato simplificado da ANPD), decidir sobre um encarregado nominal mesmo dispensado.
3. Cobrança de minutos (doc 08, item 6c): parecer sobre Anatel (revenda de STFC) e CDC antes de cobrar qualquer coisa.
4. Contrato de operador com Oracle, Google e Grandstream: conferir os termos padrão (todos têm DPA) e arquivar a referência.
5. Regulamento do ECA Digital sobre modulação por porte (art. 39, §3º) ainda não saiu; acompanhar.
6. Verificação do responsável (LGPD art. 14, §5º): hoje e-mail confirmado + declaração. Se a ANPD ou o regulamento do ECA Digital pedirem mais, opções de baixa fricção: confirmação por ligação automática para o celular cadastrado, ou Pix de valor simbólico (identifica CPF).
7. Relatório de impacto (RIPD): dispensado para pequeno porte sem alto risco; a ONG pode fazer um curto mesmo assim, usando a seção 2 como base.

## Fontes consultadas em 27/10/2026

Texto da Lei 15.211/2025 no Planalto; LGPD art. 14 e Enunciado CD/ANPD 1/2023 (via Lefosse, Machado Meyer, Conjur); Resolução CD/ANPD 2/2022 (gov.br/anpd); Resolução CD/ANPD 15/2024 (via Migalhas, Confidata, Cescon Barrieu); Resolução CD/ANPD 19/2024 (via Mattos Filho, Lefosse); Marco Civil art. 15 (Planalto) e análises (Conjur 2025); jurisprudência CDC x associações (TJBA citando STJ REsp 2.173.952); Grandstream "How GDMS Processes User Data" (ago/2024) e GDMS Security Whitepaper; localização do servidor (ipinfo: Oracle, São Paulo).
