#!/usr/bin/env bash
# geoip.sh — liga a conferencia do fuso da familia pelo IP do telefone (rede/geoip.py) no servidor da bancada.
#   deploy/geoip.sh ~/.config/rede-aberta/bancada.env
# Le GEOIP_ACCOUNT_ID e GEOIP_LICENSE_KEY (conta gratuita GeoLite2 em maxmind.com: Account > Manage License Keys),
# alem de BANCADA_IP e BANCADA_SSH_KEY. O que faz, por SSH, como root:
#   1. apt install geoipupdate (traz o timer semanal) e grava /etc/GeoIP.conf (600 root, so GeoLite2-City)
#   2. baixa a base agora em /var/lib/GeoIP/GeoLite2-City.mmdb e liga o geoipupdate.timer
#   3. pip install maxminddb no venv do portal e REDE_GEOIP_DB no portal.env; reinicia o portal
# A base e consultada no proprio servidor: nenhum IP de familia sai para terceiros. Nunca imprime a chave.
# Idempotente.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}" "${GEOIP_ACCOUNT_ID:?}" "${GEOIP_LICENSE_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")

echo "==> Instalando geoipupdate e a base GeoLite2-City"
"${SSH[@]}" "sudo GEOIP_ACCOUNT_ID='$GEOIP_ACCOUNT_ID' GEOIP_LICENSE_KEY='$GEOIP_LICENSE_KEY' bash -s" <<'REMOTO'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq geoipupdate >/dev/null
umask 077
cat > /etc/GeoIP.conf <<CONF
# Gerado por deploy/geoip.sh. Conta GeoLite2 (gratuita) da MaxMind; so a base de cidades, que traz o fuso.
AccountID $GEOIP_ACCOUNT_ID
LicenseKey $GEOIP_LICENSE_KEY
EditionIDs GeoLite2-City
DatabaseDirectory /var/lib/GeoIP
CONF
chmod 600 /etc/GeoIP.conf; chown root:root /etc/GeoIP.conf
install -d -m 755 /var/lib/GeoIP
geoipupdate -v 2>&1 | grep -vi "licensekey" || true
test -f /var/lib/GeoIP/GeoLite2-City.mmdb || { echo "geoipupdate nao baixou a base: conferir GEOIP_ACCOUNT_ID e GEOIP_LICENSE_KEY"; exit 1; }
chmod 644 /var/lib/GeoIP/GeoLite2-City.mmdb
systemctl enable --now geoipupdate.timer >/dev/null 2>&1 || true
ls -la /var/lib/GeoIP/GeoLite2-City.mmdb

PORTAL=/opt/rede-aberta/portal
sudo -u rede /opt/rede-aberta/venv/bin/pip install -q maxminddb
ENVP=/etc/rede-aberta/portal.env
grep -q '^REDE_GEOIP_DB=' "$ENVP" || printf '\n# Base GeoLite2-City (deploy/geoip.sh): conferencia do fuso da familia pelo IP do telefone\nREDE_GEOIP_DB=/var/lib/GeoIP/GeoLite2-City.mmdb\n' >> "$ENVP"
systemctl restart rede-portal
cd "$PORTAL" && sudo -u rede REDE_ENV_FILE="$ENVP" /opt/rede-aberta/venv/bin/python3 - <<'PY'
import os
for l in open(os.environ['REDE_ENV_FILE']):
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); os.environ.setdefault(k, v.strip('"'))
from rede.config import Config
from rede import geoip
cfg = Config()
print('base disponivel:', geoip.disponivel(cfg), '| 200.160.2.3 (Registro.br, SP) ->', geoip.fuso_do_ip('200.160.2.3', cfg))
PY
REMOTO
echo "==> Pronto. Casos 'fuso_divergente' aparecem no painel quando o IP do telefone nao bate com o fuso da familia."
