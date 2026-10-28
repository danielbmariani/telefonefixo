#!/usr/bin/env bash
# endurecer.sh — endurecimento do servidor (auditoria de seguranca, doc 14). Idempotente.
#   deploy/endurecer.sh [arquivo.env]
# nginx (cabecalhos, limites de taxa, TLS 1.2+, sem versao, log do /p/ sem token), fail2ban (ssh, asterisk,
# nginx), Asterisk (so chan_pjsip; log de seguranca), rpcbind desligado, permissoes do portal sem escrita
# de grupo, systemd com sandbox, backup diario do banco, atualizacoes pendentes. Reinicia nginx, asterisk
# e o portal. NAO reinicia a maquina: avisa se for preciso.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -C "$AQUI/deploy" -czf "$TMP/seg.tgz" seguranca nginx-rede.conf
"${SSH[@]}" "sudo rm -rf /tmp/seg-envio && mkdir -p /tmp/seg-envio"
scp -i "$SSH_KEY" -q "$TMP/seg.tgz" "ubuntu@$BANCADA_IP:/tmp/seg-envio/"
"${SSH[@]}" "sudo bash -s" <<'REMOTO'
set -euo pipefail
cd /tmp/seg-envio && tar xzf seg.tgz
S=/tmp/seg-envio/seguranca
echo "[1/8] nginx"
install -m 644 $S/nginx-rede-seguranca.conf /etc/nginx/conf.d/rede-seguranca.conf
install -m 644 $S/nginx-rede-headers.conf /etc/nginx/snippets/rede-headers.conf
install -m 644 $S/nginx-rede-locations.conf /etc/nginx/snippets/rede-locations.conf
sed -i -E 's/^(\s*)ssl_protocols .*/\1ssl_protocols TLSv1.2 TLSv1.3;/' /etc/nginx/nginx.conf
grep -q '^\s*ssl_ciphers' /etc/nginx/nginx.conf || sed -i -E 's/^(\s*)ssl_prefer_server_ciphers on;/\1ssl_prefer_server_ciphers off;\n\1ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;/' /etc/nginx/nginx.conf
# sites: regenera o do dominio novo a partir do modelo; o antigo (duckdns) ganha os cabecalhos e o log sem token
for site in /etc/nginx/sites-available/rede-*.org; do
  [ -f "$site" ] || continue
  DOM=$(basename "$site" | sed 's/^rede-//')
  sed "s/TROCAR_DOMINIO/$DOM/g" /tmp/seg-envio/nginx-rede.conf > "$site"
done
# dominio antigo: cabecalhos + log de prov sem token
A=/etc/nginx/sites-available/rede
if [ -f $A ] && ! grep -q rede-headers $A; then
  sed -i 's|    add_header Strict-Transport-Security "max-age=31536000" always;|    include snippets/rede-headers.conf;|' $A
  sed -i 's|access_log /var/log/nginx/rede-prov.log combined;|access_log /var/log/nginx/rede-prov.log rede_prov;|' $A
fi
nginx -t && systemctl reload nginx
echo "[2/8] fail2ban"
DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban >/dev/null
install -m 644 $S/fail2ban-jail.local /etc/fail2ban/jail.local
echo "[3/8] asterisk: so pjsip; log de seguranca"
for m in chan_iax2 chan_unistim chan_console chan_motif chan_audiosocket res_phoneprov; do
  grep -q "^noload = $m.so" /etc/asterisk/modules.conf || sed -i "/^noload = chan_sip.so/a noload = $m.so" /etc/asterisk/modules.conf
done
grep -q '^security.log => security' /etc/asterisk/logger.conf || echo 'security.log => security' >> /etc/asterisk/logger.conf
install -m 644 $S/logrotate-asterisk-rede /etc/logrotate.d/asterisk-rede
rm -f /var/log/asterisk/messages.log.[0-9]* 2>/dev/null || true
systemctl restart asterisk; sleep 3
systemctl enable --now fail2ban >/dev/null; systemctl restart fail2ban
echo "[4/8] rpcbind desligado"
systemctl disable --now rpcbind.socket rpcbind.service >/dev/null 2>&1 || true
echo "[5/8] permissoes do portal"
chmod -R g-w /opt/rede-aberta/portal; chmod 755 /opt/rede-aberta/portal/agi/*.py
echo "[6/8] systemd sandbox"
for u in rede-portal rede-jobs rede-diario; do mkdir -p /etc/systemd/system/$u.service.d; install -m 644 $S/systemd-endurecimento.conf /etc/systemd/system/$u.service.d/endurecimento.conf; done
systemctl daemon-reload; systemctl restart rede-portal; sleep 2
echo "[7/8] backup diario do banco"
install -m 755 $S/rede-backup-db /usr/local/sbin/rede-backup-db
install -m 644 $S/rede-backup.cron /etc/cron.d/rede-backup
/usr/local/sbin/rede-backup-db && ls -la /var/backups/rede-aberta/db | tail -1
echo "[8/8] atualizacoes"
DEBIAN_FRONTEND=noninteractive apt-get -y -q upgrade >/dev/null 2>&1 || echo "aviso: apt upgrade com erro"
echo "--- verificacao"
systemctl is-active nginx asterisk rede-portal fail2ban | tr '\n' ' '; echo
fail2ban-client status | tr -d '\n' | sed 's/\s\+/ /g'; echo
asterisk -rx "module show like chan_" | awk '{print $1}' | grep chan_ | tr '\n' ' '; echo
asterisk -rx "pjsip show registrations" | grep -c Registered
curl -s -o /dev/null -w "portal local: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar
ss -tlnH | awk '{print $4}' | sort -u | tr '\n' ' '; echo
[ -f /var/run/reboot-required ] && echo "REBOOT PENDENTE (kernel)" || echo "sem reboot pendente"
rm -rf /tmp/seg-envio
REMOTO
echo "==> FIM"
