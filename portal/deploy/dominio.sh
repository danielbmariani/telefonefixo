#!/usr/bin/env bash
# dominio.sh — poe o site num dominio novo (ex.: telefonefixo.org), mantendo o antigo no ar.
#   deploy/dominio.sh telefonefixo.org [email-letsencrypt] [arquivo.env]
# Antes: registrar o dominio e criar dois registros DNS tipo A, "@" e "www", apontando para BANCADA_IP
# (sem proxy/CDN). O script confere o DNS, emite o certificado, configura o nginx, troca
# REDE_SITE_URL/REDE_PROV_URL e registra de novo o webhook do GDMS. O dominio antigo continua
# respondendo: os telefones ja configurados buscam o cfg nele (P237) ate receberem config nova.
set -euo pipefail
DOM="${1:?dominio}"; LE_EMAIL="${2:-}"; ENVF="${3:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> DNS"
# Dominio recem-registrado: um resolvedor pode ter guardado "nao existe" por alguns minutos; tenta varios.
for h in "$DOM" "www.$DOM"; do
  ip=""
  for r in 1.1.1.1 8.8.8.8 9.9.9.9; do ip=$(dig +short A "$h" @$r | tail -1 || true); [ "$ip" = "$BANCADA_IP" ] && break; done
  if [ "$ip" != "$BANCADA_IP" ]; then echo "ERRO: $h resolve para '${ip:-nada}', esperado $BANCADA_IP. Crie/espere o DNS e rode de novo."; exit 1; fi
  echo "$h -> $ip ok"
done

scp -i "$SSH_KEY" -q "$AQUI/deploy/nginx-rede.conf" "ubuntu@$BANCADA_IP:/tmp/nginx-rede.conf"
"${SSH[@]}" "sudo env DOM='$DOM' LE_EMAIL='$LE_EMAIL' bash -s" <<'REMOTO'
set -euo pipefail
ENVP=/etc/rede-aberta/portal.env; PORTAL=/opt/rede-aberta/portal; VENV=/opt/rede-aberta/venv
SITE=/etc/nginx/sites-available/rede-$DOM
echo "[1/4] nginx http (ACME) para $DOM"
cat > $SITE <<N
server {
    listen 80;
    server_name $DOM www.$DOM;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$DOM\$request_uri; }
}
N
ln -sf $SITE /etc/nginx/sites-enabled/rede-$DOM; nginx -t && systemctl reload nginx
echo "[2/4] certificado"
if [ ! -f /etc/letsencrypt/live/$DOM/fullchain.pem ]; then
  if [ -n "$LE_EMAIL" ]; then EM=(--email "$LE_EMAIL"); else EM=(--register-unsafely-without-email); fi
  certbot certonly --webroot -w /var/www/html -d "$DOM" -d "www.$DOM" --agree-tos -n "${EM[@]}"
fi
echo "[3/4] nginx https"
{ cat <<N
server {
    listen 80;
    server_name $DOM www.$DOM;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$DOM\$request_uri; }
}
server {
    listen 443 ssl http2;
    server_name www.$DOM;
    ssl_certificate /etc/letsencrypt/live/$DOM/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOM/privkey.pem;
    return 301 https://$DOM\$request_uri;
}
N
  sed "s/TROCAR_DOMINIO/$DOM/g" /tmp/nginx-rede.conf | sed '1,/^}/d'   # so o bloco 443 do modelo
} > $SITE
nginx -t && systemctl reload nginx
echo "[4/4] portal.env, portal e webhook do GDMS"
sed -i -e "s|^REDE_SITE_URL=.*|REDE_SITE_URL=https://$DOM|" -e "s|^REDE_PROV_URL=.*|REDE_PROV_URL=https://$DOM|" $ENVP
systemctl restart rede-portal; sleep 2
sudo -u rede bash -c "set -a; . $ENVP; set +a; cd $PORTAL && FLASK_APP=wsgi:app $VENV/bin/flask gdms-eventos" 2>&1 | tail -3 || echo "aviso: webhook nao registrado (rode flask gdms-eventos depois)"
curl -s -o /dev/null -w "https://$DOM/entrar: HTTP %{http_code}\n" "https://$DOM/entrar"
curl -s -o /dev/null -w "https://www.$DOM -> %{redirect_url}\n" "https://www.$DOM/"
rm -f /tmp/nginx-rede.conf
REMOTO
echo "==> FIM. Atualize BANCADA_DOMINIO em $ENVF se quiser que os scripts usem o novo dominio."
