# 14. Auditoria de segurança (27/10/2026)

Varredura pedida pelo Daniel antes de abrir o site a famílias de fora. Quatro frentes: código do portal,
testes dinâmicos (local e contra o site no ar), servidor da bancada e configuração da central. O que
pôde ser corrigido no código foi corrigido e está no ar; o endurecimento do servidor está pronto em
`portal/deploy/endurecer.sh` e **aguarda autorização** porque instala pacote, reinicia serviços e
aplica atualizações do sistema (ver seção 4).

Gravidade: **alta** = permite acesso a dados de outra família ou controle do servidor; **média** = facilita
ataque ou amplia dano; **baixa** = boa prática.

## 1. O que foi verificado e está bem

| Área | Verificação | Resultado |
|---|---|---|
| Acesso entre famílias | família B tentando ver ou alterar telefone, contatos, horários, histórico, cartão, turmas e senha do aparelho da criança de A (7 rotas GET, 2 POST) | 404 em todas; `crianca_da_familia` em todas as rotas |
| Exportação | `/meus-dados.json` | só a própria família |
| Painel da ONG | família comum em `/ong/*` | 403; operador exige papel `operador`/`admin` |
| CSRF | POST sem token, com token errado, com token de outro usuário | 403 nos três; verificação global em `before_request`, só `/p/` e `/gdms/eventos/` isentos (não usam sessão) |
| Login | 5 tentativas por IP em 15 min; mesma mensagem para e-mail inexistente; `session.clear()` no login (sem fixação de sessão); cookie `Secure`, `HttpOnly`, `SameSite=Lax` | ok |
| Senhas | PBKDF2-SHA256, 100 mil iterações, sal por senha, comparação em tempo constante | ok |
| Código de e-mail | 6 dígitos, 5 tentativas, expira em 10 min, 3 códigos por hora | ok |
| Reset de senha | token de 32 bytes, guardado como SHA-256, uso único, 1 hora, mensagem genérica | ok |
| Provisionamento `/p/<token>/cfg<mac>.xml` | token de 43 caracteres aleatórios; MAC tem de bater; 60 pedidos por hora por IP; 404 igual para qualquer erro; token revogado e caso aberto se outro MAC usar o mesmo token | ok |
| Webhook do GDMS | segredo no caminho comparado em tempo constante; 404 sem ele; 600 por minuto por IP; corpo limitado a 1 MB | ok |
| XSS | mensagem de apresentação e apelidos com HTML | escapados pelo Jinja; os três `|safe` são `json.dumps` de dados sem HTML |
| SQL | consultas com SQLAlchemy Core; os `text()` usam parâmetros; a única concatenação é de uma condição fixa | ok |
| Redirecionamento aberto | parâmetro `next` | não existe |
| TLS | TLS 1.0 e 1.1 recusados; 1.2 e 1.3 aceitos; HSTS; HTTP redireciona | ok |
| Portas na internet | 22 (só chave SSH, sem senha, sem root por senha), 80, 443, 5060 TCP/UDP, RTP 10000 a 20000. Resto rejeitado pelo iptables | ok |
| Postgres | só `localhost`, `scram-sha-256`; papel do portal sem `UPDATE/DELETE` nas tabelas de auditoria | ok |
| Segredos | nenhum no repositório (`portal.env` e `*.env` ignorados; busca por padrões de senha/token); `portal.env` 640 root:rede; `pjsip_tronco.conf` 640 asterisk | ok |
| Central telefônica | sem caminho no dialplan para números arbitrários (só IDs e 9/8 + o próprio ID); senhas SIP de 24 caracteres aleatórios; AMI só em `localhost`; sem endpoint anônimo (robôs recebem 401) | ok |
| Dependências | Flask 3.1.3, Werkzeug 3.1.9, Jinja2 3.1.6, SQLAlchemy 2.0.55, gunicorn 26.2.0, psycopg2 2.9.13 (versões de 2026) | ok; sem `pip-audit` disponível para confirmar CVEs |

## 2. Achados corrigidos hoje no código (no ar)

| Grav. | Achado | Correção |
|---|---|---|
| média | Senha `12345678` era aceita (só exigia 8 caracteres) | lista de senhas óbvias, repetições, sequências e senha igual ao e-mail recusadas (`seguranca.senha_fraca`) no cadastro e no reset |
| média | Limite de login só por IP: ataque distribuído contra um e-mail passava | limite também por conta (15 em 15 min), registrado na auditoria |
| média | Cadastro revelava e-mail existente ("Se este e-mail já tiver conta...") e a verificação dizia "Nenhum cadastro em andamento" | mesma tela de sucesso para todos; dono do e-mail recebe aviso; mensagens genéricas |
| média | Sem `Content-Security-Policy` nem `Permissions-Policy` | ambos no Flask (`after_request`) e no nginx (snippet) |
| baixa | Sessão sem prazo | 12 horas, renovada a cada acesso |

## 3. Achados no servidor (corrigidos com `deploy/endurecer.sh` em 27/10, 15h10, com autorização do Daniel; máquina reiniciada 15h13, kernel 7.0.0-1013)

| Grav. | Achado | O que o script faz |
|---|---|---|
| **alta** | **Não havia backup do banco.** Só a auditoria era exportada. Uma falha de disco ou um `DROP TABLE` apagaria famílias, crianças e telefones sem volta | `pg_dump` diário às 3h30, 14 dias, 600 root, em `/var/backups/rede-aberta/db`. Cópia fora do servidor fica como item 4.6 |
| média | Sem fail2ban: scanners SIP e tentativas de login não são banidos | fail2ban com jails `sshd`, `asterisk` (log de segurança ligado), `nginx-limit-req`, `nginx-botsearch` |
| média | Limite de taxa só no Flask, por processo (2 workers = limite dobrado e não compartilhado) | `limit_req` no nginx: login/cadastro/reset 10 por minuto por IP, `/p/` 30 por minuto, geral 300 por minuto |
| média | Token de provisionamento e segredo do webhook aparecem na URL nos logs do nginx (grupo `adm` lê) | formato de log do `/p/` sem URL; `/gdms/` sem log de acesso (o portal já registra tudo em `prov_log` e `gdms_log`) |
| média | `/opt/rede-aberta/portal` com escrita de grupo e o usuário `asterisk` no grupo `rede`: quem comprometer o Asterisk edita o código do portal | `chmod -R g-w`; `asterisk` continua só lendo (precisa do `portal.env` para os AGIs) |
| média | Kernel novo instalado e 19 pacotes pendentes; **reinício pendente** | `apt upgrade`; o reinício fica para o Daniel decidir (1 minuto fora do ar, telefones re-registram sozinhos) |
| baixa | Asterisk carrega `chan_iax2` (porta 4569), `chan_unistim`, `chan_console`, `chan_motif` sem uso (iptables bloqueia, mas é superfície) | `noload` nesses módulos |
| baixa | `rpcbind` ativo (porta 111, bloqueada pelo iptables) | desligado |
| baixa | nginx anuncia a versão; `ssl_protocols` no `nginx.conf` ainda lista TLS 1.0/1.1 (recusados só porque o OpenSSL impede) | `server_tokens off`; TLS 1.2/1.3 e cifras modernas explícitas |
| baixa | Serviços systemd sem sandbox | `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `ProtectHome` etc. nos três serviços |
| baixa | `X11Forwarding yes` no SSH | não alterado (chaves apenas; mudar exige mexer no sshd, fica para depois) |

Aplicado e conferido: 4 jails do fail2ban ativas; só `chan_pjsip` carregado; backup `telefone-20261027-1509.sql.gz`
(181 KB, 600 root); `limit_req` devolvendo 429 no 12º pedido a `/entrar`; cabeçalhos servidos pelo nginx sem
duplicar os do Flask; `www` redireciona; após o reinício, tronco registrado e os dois GRP de volta em menos de
2 minutos. Para refazer em outro servidor: `portal/deploy/endurecer.sh <env>`.

## 4. Riscos que ficam, por desenho ou por decisão

1. **Falsificação do número do celular** (entrada pelo tronco): quem conseguir enviar o identificador da mãe fala com a criança. Difícil nas operadoras brasileiras, não impossível. Correção definitiva anotada em B23: a central desliga e liga de volta para o número cadastrado. Fazer antes de abrir para muitas famílias.
2. **Cloudflare, Nvoip, Oracle, Grandstream e Google** são pontos de confiança: quem controlar a conta do Daniel em qualquer um deles controla domínio, tronco, servidor, telefones ou e-mail. Ligar autenticação em dois fatores nas cinco contas é a medida mais barata e mais eficaz que existe hoje. **A senha do GDMS que apareceu no chat em 26/10 ainda não foi trocada.** O painel da Nvoip não oferece 2FA (conferido no menu da conta em 27/10; nada na base de conhecimento nem no termo de uso). Mitigação enquanto não houver: senha longa e única só no gerenciador, 2FA forte no e-mail de cadastro (que é o canal de recuperação), e pedir o recurso por ticket ao suporte.
3. **Regra de segurança da Oracle (VCN)**: conferida em 27/10 pela OCI CLI. A security list da `subnet-publica` libera exatamente TCP 22, 80, 443 e 5060, UDP 5060 e 10000 a 20000, e ICMP tipo 3; tudo de 0.0.0.0/0, sem NSG. Bate com o que escuta e com o iptables; TCP 5060 é necessário porque os GRP2601 registram por TCP (o tronco Nvoip usa UDP). A VM do projeto antigo, `asterisk-telefone` (<ip da VM antiga>, telefone-fixo.duckdns.org), continua em produção na mesma subnet e fica (decisão do Daniel em 27/10); ela responde em 22, 80, 443 e 5060 e divide esta security list, então qualquer mudança aqui afeta as duas. Para repetir a conferência: `oci network security-list list --compartment-id <tenancy> --vcn-id <vcn>`.
4. **Verificação do responsável**: e-mail confirmado + declaração. Qualquer adulto pode se cadastrar como "família". A autorização mútua limita o dano (ninguém fala com uma criança sem o sim da família dela), mas o canal de denúncias precisa ser lido.
5. **Limite de taxa em memória** continua existindo como segunda camada; a primeira passa a ser o nginx. Com mais de um servidor, trocar por Redis.
6. **Cópia externa do backup** (item 3): um `rclone` para um bucket da Oracle Object Storage ou do Backblaze, criptografado. Sem isso, backup e banco morrem juntos num incidente de conta.
7. **Registro de acesso do nginx** guarda IPs por 6 meses; é dado pessoal com finalidade de segurança, declarado na política.

## 5. Checklist antes do piloto com famílias de fora

- [x] Rodar `endurecer.sh` e reiniciar a máquina (27/10).
- [ ] 2FA na Cloudflare, Oracle, GDMS e Google; trocar a senha do GDMS.
- [ ] Nvoip (sem 2FA no painel): senha única no gerenciador e ticket pedindo 2FA.
- [x] Conferir a security list da VCN na Oracle (27/10, sem sobras).
- [ ] Criar `contato@` e `privacidade@` no Email Routing da Cloudflare e testar.
- [ ] Cópia externa do backup.
- [ ] Repetir esta auditoria depois de qualquer mudança no dialplan ou nas rotas do portal (os testes em `tests/test_seguranca.py`, `test_lgpd.py` e o roteiro `scratchpad/audit_dyn.py` cobrem o essencial).
