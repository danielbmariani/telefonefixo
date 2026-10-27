#!/bin/bash
# setup-servidor.sh — instala a Rede Aberta (portal + Asterisk realtime + Postgres + nginx/HTTPS)
# num Ubuntu 24.04 limpo, via SSH. Idempotente: pode rodar de novo para atualizar o portal.
#
# Uso (na maquina do Daniel):
#   deploy/setup-servidor.sh ~/.config/rede-aberta/bancada.env
#
# O arquivo .env (chmod 600, fora do git) tem:
#   BANCADA_IP=1.2.3.4
#   BANCADA_SSH_KEY=/home/daniel/.ssh/rede-aberta-bancada.key
#   BANCADA_DOMINIO=rede-aberta-bancada.duckdns.org
#   DUCKDNS_TOKEN=...            (opcional: cron que mantem o DNS apontando para a VM)
#   LE_EMAIL=...                 (opcional: e-mail do Let's Encrypt; padrao: nenhum)
#   GDMS_ENV=/home/daniel/.config/rede-aberta/gdms.env   (opcional: copia as credenciais REDE_GDMS_*)
#
# Segredos gerados na primeira vez (senhas do Postgres, SECRET_KEY, segredo do webhook, senha do
# operador) ficam em /root/rede-aberta-segredos.env no servidor e a senha do operador tambem em
# ~/.config/rede-aberta/bancada-operador.txt aqui.

set -euo pipefail

ENV_FILE="${1:-$HOME/.config/rede-aberta/bancada.env}"
[ -f "$ENV_FILE" ] || { echo "arquivo de ambiente nao encontrado: $ENV_FILE"; exit 1; }
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}" "${BANCADA_DOMINIO:?}"
DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-}"
LE_EMAIL="${LE_EMAIL:-}"
GDMS_ENV="${GDMS_ENV:-$HOME/.config/rede-aberta/gdms.env}"
SSH_USER=ubuntu
SSH_OPTS=(-i "$BANCADA_SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJETO_ATUAL="$(cd "$PORTAL_DIR/../../telefone_fixo" 2>/dev/null && pwd || true)"

echo "==> Empacotando portal"
TMP=$(mktemp -d)
mkdir -p "$TMP/envio/portal" "$TMP/envio/sons/telefone" "$TMP/envio/sons/grupo" "$TMP/envio/sons/hora"
tar -C "$PORTAL_DIR" --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
    --exclude='*.db' --exclude='tests' -cf - rede agi deploy wsgi.py requirements.txt pytest.ini \
    | tar -C "$TMP/envio/portal" -xf -
if [ -n "$PROJETO_ATUAL" ] && [ -d "$PROJETO_ATUAL/web/deploy/grupo-audio" ]; then
  cp "$PROJETO_ATUAL"/web/deploy/grupo-audio/mensagens-asterisk/*.wav "$TMP/envio/sons/telefone/" 2>/dev/null || true
  cp "$PROJETO_ATUAL"/web/deploy/grupo-audio/hora2-asterisk/*.wav "$TMP/envio/sons/hora/" 2>/dev/null || true
  for n in 2 3 4; do cp "$PROJETO_ATUAL/web/deploy/grupo-audio/entrando-$n.wav" "$TMP/envio/sons/grupo/" 2>/dev/null || true; done
fi
if [ -f "$GDMS_ENV" ]; then cp "$GDMS_ENV" "$TMP/envio/gdms.env"; fi
tar -C "$TMP" -czf "$TMP/envio.tgz" envio
echo "    $(du -h "$TMP/envio.tgz" | cut -f1)"

echo "==> Enviando para $BANCADA_IP"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$BANCADA_IP" "sudo rm -rf /tmp/rede-envio && mkdir -p /tmp/rede-envio"
scp "${SSH_OPTS[@]}" -q "$TMP/envio.tgz" "$SSH_USER@$BANCADA_IP:/tmp/rede-envio/envio.tgz"

REMOTO="$TMP/remoto.sh"
cat > "$REMOTO" <<'REMOTE_EOF'
#!/bin/bash
set -euo pipefail
VPS_IP="__VPS_IP__"; DOMINIO="__DOMINIO__"; DUCKDNS_TOKEN="__DUCKDNS_TOKEN__"; LE_EMAIL="__LE_EMAIL__"
SRC=/tmp/rede-envio/envio
BASE=/opt/rede-aberta; VENV=$BASE/venv; PORTAL=$BASE/portal
SEGREDOS=/root/rede-aberta-segredos.env
AST_VER=20.6.0

passo() { echo; echo "==> $*"; }

cd /tmp/rede-envio && tar xzf envio.tgz

passo "[1/11] Pacotes"
timedatectl set-timezone America/Sao_Paulo
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq asterisk asterisk-modules postgresql unixodbc odbc-postgresql \
  python3 python3-venv python3-pip nginx certbot python3-certbot-nginx iptables-persistent \
  curl sox espeak-ng libpq-dev >/dev/null

passo "[2/11] Segredos"
if [ ! -f "$SEGREDOS" ]; then
  gen() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
  cat > "$SEGREDOS" <<S
PG_PORTAL_SENHA=$(gen 32)
PG_ASTERISK_SENHA=$(gen 32)
SECRET_KEY=$(gen 64)
WEBHOOK_SEGREDO=$(gen 48)
OPERADOR_SENHA=$(gen 16)
S
  chmod 600 "$SEGREDOS"
fi
# shellcheck disable=SC1090
. "$SEGREDOS"

passo "[3/11] Postgres"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='telefone'" | grep -q 1 || \
  sudo -u postgres createdb telefone
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='portal'" | grep -q 1 || \
  sudo -u postgres psql -qc "CREATE ROLE portal LOGIN PASSWORD '$PG_PORTAL_SENHA'"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='asterisk'" | grep -q 1 || \
  sudo -u postgres psql -qc "CREATE ROLE asterisk LOGIN PASSWORD '$PG_ASTERISK_SENHA'"
sudo -u postgres psql -qc "ALTER ROLE portal PASSWORD '$PG_PORTAL_SENHA'; ALTER ROLE asterisk PASSWORD '$PG_ASTERISK_SENHA';"

passo "[4/11] Usuario, codigo e venv do portal"
id rede >/dev/null 2>&1 || useradd -r -m -d $BASE -s /usr/sbin/nologin rede
mkdir -p $PORTAL /etc/rede-aberta /var/backups/rede-aberta/auditoria /var/log/rede-aberta
rsync -a --delete --exclude 'rede-dev.db' "$SRC/portal/" "$PORTAL/" 2>/dev/null || cp -r "$SRC/portal/." "$PORTAL/"
[ -d $VENV ] || python3 -m venv $VENV
$VENV/bin/pip install -q --upgrade pip
$VENV/bin/pip install -q -r $PORTAL/requirements.txt gunicorn
# O alembic do Asterisk (contrib/ast-db-manage) foi escrito para SQLAlchemy 1.x: com 2.x roda sem
# erro mas nao faz commit (nenhuma tabela aparece). Venv separado.
[ -d $BASE/venv-alembic ] || python3 -m venv $BASE/venv-alembic
$BASE/venv-alembic/bin/pip install -q "sqlalchemy<2" "alembic<1.14" psycopg2-binary
rm -f $PORTAL/rede-dev.db
chown -R rede:rede $BASE /var/backups/rede-aberta /var/log/rede-aberta

passo "[5/11] Tabelas ps_* do Asterisk (alembic oficial, config schema)"
if ! sudo -u postgres psql -d telefone -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='ps_endpoints'" | grep -q 1; then
  cd /tmp
  [ -d asterisk-$AST_VER ] || { curl -fsSL "https://downloads.asterisk.org/pub/telephony/asterisk/releases/asterisk-$AST_VER.tar.gz" -o ast.tgz \
      && tar xzf ast.tgz asterisk-$AST_VER/contrib/ast-db-manage; }
  cd asterisk-$AST_VER/contrib/ast-db-manage
  sed "s|^sqlalchemy.url.*|sqlalchemy.url = postgresql://portal:$PG_PORTAL_SENHA@localhost/telefone|" config.ini.sample > config.ini
  # O alembic cria as tabelas como 'portal' (dono). Tabelas sem dono postgres facilitam os grants.
  sudo -u postgres psql -d telefone -qc "GRANT ALL ON SCHEMA public TO portal"
  $BASE/venv-alembic/bin/alembic -c config.ini upgrade head
fi

passo "[6/11] portal.env e tabelas do portal"
ENVF=/etc/rede-aberta/portal.env
if [ ! -f $ENVF ]; then
  cat > $ENVF <<E
REDE_AMBIENTE=producao
REDE_NOME="Telefone Fixo"
REDE_SECRET_KEY=$SECRET_KEY
REDE_DATABASE_URL=postgresql+psycopg2://portal:$PG_PORTAL_SENHA@localhost/telefone
REDE_SITE_URL=https://$DOMINIO
REDE_PROV_URL=https://$DOMINIO
REDE_SIP_HOST=$VPS_IP
REDE_MAIL_BACKEND=console
REDE_MAIL_FROM=rede@$DOMINIO
REDE_GDMS_MODO=simulado
REDE_GDMS_BASE_URL=https://www.gdms.cloud
REDE_GDMS_ORG_ID=__GDMS_ORG_ID__
REDE_GDMS_SITE_ID=0
REDE_GDMS_ENVIO_MODO=api
REDE_GDMS_XML_CONTEUDO=ponteiro
REDE_GDMS_WEBHOOK_SEGREDO=$WEBHOOK_SEGREDO
REDE_MODELO_PADRAO=grp
E
  if [ -f "$SRC/gdms.env" ]; then grep '^REDE_GDMS_' "$SRC/gdms.env" >> $ENVF; fi
fi
chown root:rede $ENVF; chmod 640 $ENVF
cd $PORTAL
sudo -u rede bash -c "set -a; . $ENVF; set +a; FLASK_APP=wsgi:app $VENV/bin/flask init-db"
# Dono das tabelas = postgres, nao o papel da aplicacao. Motivo: a checagem de chave estrangeira
# (device_state_history.audit_id -> audit_log) roda como dono da tabela com SELECT ... FOR KEY SHARE,
# que exige UPDATE; se o dono for 'portal' (com UPDATE revogado em audit_log), todo INSERT falha.
sudo -u postgres psql -d telefone -q <<SQL
REASSIGN OWNED BY portal TO postgres;
GRANT USAGE ON SCHEMA public TO portal, asterisk;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO portal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO portal;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log, device_state_history, prov_log, gdms_log FROM portal;
GRANT SELECT ON ps_endpoints, ps_auths, ps_aors TO asterisk;
GRANT SELECT, INSERT, UPDATE, DELETE ON ps_contacts TO asterisk;
SQL
# Operador da ONG (bancada)
sudo -u rede bash -c "set -a; . $ENVF; set +a; FLASK_APP=wsgi:app $VENV/bin/flask criar-operador \
  ong@$DOMINIO '$OPERADOR_SENHA' --nome 'Operador bancada' --papel admin" 2>/dev/null || true

passo "[7/11] Asterisk realtime"
cat > /etc/asterisk/pjsip.conf <<P
; Gerado por setup-servidor.sh. Ramais vem do Postgres (sorcery.conf/extconfig.conf).
[transport-udp]
type = transport
protocol = udp
bind = 0.0.0.0:5060
external_media_address = $VPS_IP
external_signaling_address = $VPS_IP
local_net = 10.0.0.0/8

[transport-tcp]
type = transport
protocol = tcp
bind = 0.0.0.0:5060
external_media_address = $VPS_IP
external_signaling_address = $VPS_IP
local_net = 10.0.0.0/8
P
cat > /etc/asterisk/modules.conf <<'M'
[modules]
autoload = yes
noload = chan_sip.so
load = res_odbc.so
load = res_config_odbc.so
load = res_sorcery_realtime.so
load = res_pjsip.so
load = res_pjsip_transport_udp.so
load = res_pjsip_authenticator_digest.so
load = res_pjsip_endpoint_identifier_user.so
load = res_pjsip_registrar.so
load = res_pjsip_session.so
load = chan_pjsip.so
load = app_confbridge.so
load = res_agi.so
M
cp $PORTAL/deploy/asterisk/extensions.conf $PORTAL/deploy/asterisk/confbridge.conf \
   $PORTAL/deploy/asterisk/extconfig.conf $PORTAL/deploy/asterisk/sorcery.conf /etc/asterisk/
sed "s/TROCAR_SENHA/$PG_ASTERISK_SENHA/" $PORTAL/deploy/asterisk/res_odbc.conf > /etc/asterisk/res_odbc.conf
sed "s/TROCAR_SENHA/$PG_ASTERISK_SENHA/" $PORTAL/deploy/asterisk/odbc.ini > /etc/odbc.ini
chown asterisk:asterisk /etc/asterisk/*.conf; chmod 640 /etc/asterisk/res_odbc.conf /etc/asterisk/pjsip.conf
chmod 640 /etc/odbc.ini; chown root:asterisk /etc/odbc.ini
# AGIs: rodam como asterisk com o venv do portal; precisam ler portal.env
usermod -aG rede asterisk
mkdir -p /usr/share/asterisk/agi-bin
for f in $PORTAL/agi/*.py; do chmod 755 "$f"; ln -sf "$f" /usr/share/asterisk/agi-bin/; done
# Sons
for d in telefone grupo hora; do mkdir -p /usr/share/asterisk/sounds/$d; cp "$SRC/sons/$d/"*.wav /usr/share/asterisk/sounds/$d/ 2>/dev/null || true; done
if [ ! -f /usr/share/asterisk/sounds/telefone/nao-esta-na-lista.wav ]; then
  espeak-ng -v pt-br -s 140 -w /tmp/nel.wav "Esse número não está na sua lista de contatos." 2>/dev/null \
    && sox /tmp/nel.wav -r 8000 -c 1 -b 16 /usr/share/asterisk/sounds/telefone/nao-esta-na-lista.wav || true
fi
chown -R asterisk:asterisk /usr/share/asterisk/sounds/{telefone,grupo,hora}
systemctl enable asterisk >/dev/null 2>&1 || true
systemctl restart asterisk
sleep 3
asterisk -rx "odbc show" | grep -i "connected\|asterisk" | head -3 || true
asterisk -rx "pjsip show transports" | grep -c transport || true

passo "[8/11] systemd do portal"
cp $PORTAL/deploy/rede-portal.service $PORTAL/deploy/rede-jobs.service $PORTAL/deploy/rede-jobs.timer \
   $PORTAL/deploy/rede-diario.service $PORTAL/deploy/rede-diario.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rede-portal.service rede-jobs.timer rede-diario.timer >/dev/null
systemctl restart rede-portal.service
sleep 2
curl -s -o /dev/null -w "portal local: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar || true

passo "[9/11] Firewall"
open_port() { iptables -C INPUT -p "$1" --dport "$2" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p "$1" --dport "$2" -j ACCEPT; }
open_port tcp 80; open_port tcp 443; open_port tcp 5060; open_port udp 5060; open_port udp 10000:20000
netfilter-persistent save >/dev/null 2>&1 || true

passo "[10/11] DuckDNS"
if [ -n "$DUCKDNS_TOKEN" ]; then
  echo "*/5 * * * * root curl -s 'https://www.duckdns.org/update?domains=${DOMINIO%%.duckdns.org}&token=$DUCKDNS_TOKEN&ip=' >/var/log/duckdns.log 2>&1" > /etc/cron.d/duckdns
  curl -s "https://www.duckdns.org/update?domains=${DOMINIO%%.duckdns.org}&token=$DUCKDNS_TOKEN&ip=" ; echo
fi

passo "[11/11] nginx + HTTPS"
DNS_IP=$(getent hosts "$DOMINIO" | awk '{print $1}' | head -1 || true)
cat > /etc/nginx/sites-available/rede-http <<N
server {
    listen 80;
    server_name $DOMINIO;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { proxy_pass http://127.0.0.1:5000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto \$scheme; }
}
N
rm -f /etc/nginx/sites-enabled/default
if [ "$DNS_IP" = "$VPS_IP" ]; then
  if [ ! -f /etc/letsencrypt/live/$DOMINIO/fullchain.pem ]; then
    ln -sf /etc/nginx/sites-available/rede-http /etc/nginx/sites-enabled/rede-http
    rm -f /etc/nginx/sites-enabled/rede; nginx -t && systemctl reload nginx
    if [ -n "$LE_EMAIL" ]; then EM=(--email "$LE_EMAIL"); else EM=(--register-unsafely-without-email); fi
    certbot certonly --webroot -w /var/www/html -d "$DOMINIO" --agree-tos -n "${EM[@]}"
  fi
  sed "s/TROCAR_DOMINIO/$DOMINIO/g" $PORTAL/deploy/nginx-rede.conf > /etc/nginx/sites-available/rede
  ln -sf /etc/nginx/sites-available/rede /etc/nginx/sites-enabled/rede
  rm -f /etc/nginx/sites-enabled/rede-http
  nginx -t && systemctl reload nginx
  curl -s -o /dev/null -w "https://$DOMINIO/entrar: HTTP %{http_code}\n" "https://$DOMINIO/entrar" || true
else
  echo "DNS de $DOMINIO aponta para '$DNS_IP', nao para $VPS_IP: HTTPS fica para a proxima rodada."
  ln -sf /etc/nginx/sites-available/rede-http /etc/nginx/sites-enabled/rede-http
  nginx -t && systemctl reload nginx
fi

echo
echo "==> Verificacao da auditoria append-only (deve dar 'permission denied'):"
PGPASSWORD=$PG_PORTAL_SENHA psql -h localhost -U portal -d telefone -c "UPDATE audit_log SET acao='x' WHERE id=1" 2>&1 | tail -1 || true
echo "==> Operador: ong@$DOMINIO (senha em $SEGREDOS)"
echo "==> FIM"
REMOTE_EOF

sed -i -e "s|__VPS_IP__|$BANCADA_IP|" -e "s|__DOMINIO__|$BANCADA_DOMINIO|" \
       -e "s|__DUCKDNS_TOKEN__|$DUCKDNS_TOKEN|" -e "s|__GDMS_ORG_ID__|${GDMS_ORG_ID:-0}|" -e "s|__LE_EMAIL__|$LE_EMAIL|" "$REMOTO"
scp "${SSH_OPTS[@]}" -q "$REMOTO" "$SSH_USER@$BANCADA_IP:/tmp/rede-envio/remoto.sh"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$BANCADA_IP" "sudo bash /tmp/rede-envio/remoto.sh"

mkdir -p "$HOME/.config/rede-aberta"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$BANCADA_IP" "sudo grep OPERADOR_SENHA /root/rede-aberta-segredos.env" \
  | sed "s/^/ong@$BANCADA_DOMINIO /" > "$HOME/.config/rede-aberta/bancada-operador.txt"
chmod 600 "$HOME/.config/rede-aberta/bancada-operador.txt"
rm -rf "$TMP"
echo "Senha do operador guardada em ~/.config/rede-aberta/bancada-operador.txt"
