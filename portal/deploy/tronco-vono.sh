#!/usr/bin/env bash
# tronco-vono.sh — instala/atualiza o segundo tronco (Vono, canais ilimitados, bancada B30) sem reiniciar o Asterisk.
#   deploy/tronco-vono.sh ~/.config/rede-aberta/bancada.env
# Le VONO_HOST, VONO_USUARIO, VONO_SENHA (e BANCADA_IP, BANCADA_SSH_KEY). O que faz, por SSH, como root:
#   1. grava /etc/asterisk/pjsip_vono.conf (senha so no servidor, 640 asterisk) e o #include em pjsip.conf
#   2. copia deploy/asterisk/extensions.conf (guarda o anterior em extensions.conf.antes-b30)
#   3. "pjsip reload" e "dialplan reload"; mostra o registro nos dois troncos
# Nunca imprime a senha. Idempotente. Nao mexe no portal nem reinicia nada.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}" "${VONO_HOST:?}" "${VONO_USUARIO:?}" "${VONO_SENHA:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
sed -e "s|__SERVIDOR__|$VONO_HOST|g" -e "s|__USUARIO__|$VONO_USUARIO|g" -e "s|__SENHA__|$VONO_SENHA|g" \
    "$AQUI/deploy/asterisk/pjsip_vono.conf.exemplo" > "$TMP/pjsip_vono.conf"
cp "$AQUI/deploy/asterisk/extensions.conf" "$TMP/extensions.conf"

echo "==> Enviando"
"${SSH[@]}" "sudo rm -rf /tmp/vono-envio && mkdir -p /tmp/vono-envio && chmod 700 /tmp/vono-envio"
scp -i "$SSH_KEY" -q "$TMP/pjsip_vono.conf" "$TMP/extensions.conf" "ubuntu@$BANCADA_IP:/tmp/vono-envio/"

"${SSH[@]}" "sudo bash -s" <<'REMOTO'
set -euo pipefail
echo "[1/3] pjsip_vono.conf"
install -o asterisk -g asterisk -m 640 /tmp/vono-envio/pjsip_vono.conf /etc/asterisk/pjsip_vono.conf
grep -q '^#include pjsip_vono.conf' /etc/asterisk/pjsip.conf || printf '\n#include pjsip_vono.conf\n' >> /etc/asterisk/pjsip.conf
echo "[2/3] extensions.conf"
[ -f /etc/asterisk/extensions.conf.antes-b30 ] || cp -p /etc/asterisk/extensions.conf /etc/asterisk/extensions.conf.antes-b30
install -o asterisk -g asterisk -m 640 /tmp/vono-envio/extensions.conf /etc/asterisk/extensions.conf
echo "[3/3] reload"
asterisk -rx "pjsip reload" >/dev/null
asterisk -rx "dialplan reload" >/dev/null
sleep 3
rm -rf /tmp/vono-envio
echo "--- registros"; asterisk -rx "pjsip show registrations" | grep -E "nvoip|vono"
echo "--- endpoint vono"; asterisk -rx "pjsip show endpoint vono" | grep -E "Endpoint:|Contact:|Identify|match" | head
echo "--- globals"; asterisk -rx "dialplan show globals" | grep VONO
echo "--- dialplan"; asterisk -rx "dialplan show saida-tronco" | grep -c "vono" | sed 's/^/linhas com vono em saida-tronco: /'
echo "--- erros recentes"; journalctl -u asterisk --since "-1 min" --no-pager 2>/dev/null | grep -iE "error|warning" | grep -iv "deprecat" | tail -5 || true
REMOTO
echo "==> FIM"
