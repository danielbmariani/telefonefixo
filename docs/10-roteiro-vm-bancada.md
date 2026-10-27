# 10 — Roteiro: VM e domínio da bancada

> Executado em 23/10/2026: VM `rede-aberta-bancada` (E2.1.Micro, 163.176.51.90),
> `rede-aberta-bancada.duckdns.org`, portal no ar. Resultado em `bancada/B07-portal-no-ar.md`.

Objetivo: portal da rede aberta no ar, em HTTPS, separado da rede viva, para B06b–B19.
Não mexe na VM atual (<ip da VM antiga> / telefone-fixo.duckdns.org).

## O que o Daniel faz (uma vez, ~20 min)

1. **VM na Oracle Cloud** (mesma conta). Compute > Instances > Create instance:
   - Nome: `rede-aberta-bancada`.
   - Image: Ubuntu 24.04. Shape: tente `VM.Standard.A1.Flex` (1 OCPU, 6 GB, grátis);
     se der "Out of capacity", use `VM.Standard.E2.1.Micro` (a conta free permite dois).
   - Networking: a mesma VCN/subnet pública da VM atual, "Assign a public IPv4 address".
   - SSH: "Generate a key pair for me", baixe a chave privada e guarde em
     `~/.ssh/rede-aberta-bancada.key` (`chmod 600`).
   - Depois de criada, anote o **IP público**.
2. **Security List** da subnet (Networking > VCN > Subnet > Security List > Ingress Rules).
   Se a VM nova está na mesma subnet da atual, as regras já existem (22, 80, 443, 5060, UDP 10000-20000).
   Só confira que 80 e 443 estão abertas para 0.0.0.0/0.
3. **Domínio da bancada**: em duckdns.org (mesma conta da rede atual), crie o subdomínio
   `rede-aberta-bancada` apontando para o IP novo. Anote o **token** do DuckDNS (aparece no topo da página).
4. Me passe: IP público, caminho da chave, nome do subdomínio. O token do DuckDNS vai no arquivo
   `~/.config/rede-aberta/bancada.env` (não no chat):
   ```
   BANCADA_IP=...
   BANCADA_SSH_KEY=/home/daniel/.ssh/rede-aberta-bancada.key
   BANCADA_DOMINIO=rede-aberta-bancada.duckdns.org
   DUCKDNS_TOKEN=...
   ```

## O que eu faço em seguida (via SSH)

1. Script `portal/deploy/setup-servidor.sh` (a escrever a partir do `setup-servidor.sh` atual):
   apt, Postgres, Asterisk + ODBC, tabelas `ps_*` (alembic do Asterisk), portal em `/opt/rede-aberta`,
   `portal.env` gerado com segredos novos (SECRET_KEY, senha do Postgres, segredo do webhook),
   systemd, nginx, certbot (Let's Encrypt no subdomínio DuckDNS), iptables, cron do DuckDNS.
2. Modo inicial `GDMS_MODO=simulado`, `MAIL_BACKEND=console` (e-mails vão para o log, sem SMTP).
   Teste de ponta a ponta com softphone (Groundwire/Linphone) no meu lado: cadastro → criança →
   telefone → cfg XML servido em HTTPS → registro no Asterisk → `ativo`.
3. Troca para `GDMS_MODO=real` com as credenciais da API (copio o `gdms.env` para o servidor,
   permissões 640 root:rede), `flask gdms-eventos` registra o webhook (B06c).
4. Quando o GRP2601 chegar: B06b (XML pela API com o aparelho desligado), depois B08–B11.

## O que fica para a produção (não agora)

Domínio próprio da ONG, e-mail transacional (SMTP da ONG), backup para object storage, conta
GDMS em nome da ONG, VM dimensionada (doc 06).
