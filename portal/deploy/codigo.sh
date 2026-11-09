#!/usr/bin/env bash
# codigo.sh — envia so o codigo do portal (rede/, agi/, wsgi.py), cria colunas novas e reinicia os servicos Python.
#   deploy/codigo.sh ~/.config/rede-aberta/bancada.env
# Nao instala pacote, nao mexe no Asterisk, nao toca em configuracao: e o deploy de rotina de
# template, CSS e Python. Colunas que o modelo (rede/db.py) tem e o banco nao: ALTER TABLE ... ADD COLUMN
# como postgres (dono das tabelas), antes de reiniciar, para o codigo novo nunca rodar contra o banco velho
# (aconteceu em 09/11/2026 com familias.fuso). Le BANCADA_IP e BANCADA_SSH_KEY. Nunca imprime senhas.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Empacotando codigo"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -C "$AQUI" -czf "$TMP/codigo.tgz" --exclude='__pycache__' --exclude='*.pyc' --exclude='rede-dev.db' rede agi wsgi.py
echo "==> Enviando"
"${SSH[@]}" "sudo rm -rf /tmp/codigo-envio && mkdir -p /tmp/codigo-envio && chmod 700 /tmp/codigo-envio"
scp -i "$SSH_KEY" -q "$TMP/codigo.tgz" "ubuntu@$BANCADA_IP:/tmp/codigo-envio/"

"${SSH[@]}" "sudo bash -s" <<'REMOTO'
set -euo pipefail
PORTAL=/opt/rede-aberta/portal
mkdir -p /tmp/codigo-envio/src && tar -C /tmp/codigo-envio/src -xzf /tmp/codigo-envio/codigo.tgz
# templates removidos localmente somem no servidor tambem (so dentro de rede/templates e rede/static)
for d in rede/templates rede/static; do
  rsync -a --delete --chown=rede:rede /tmp/codigo-envio/src/$d/ $PORTAL/$d/
done
(cd /tmp/codigo-envio/src && find rede agi wsgi.py -type f ! -path 'rede/templates/*' ! -path 'rede/static/*' | while read -r f; do install -D -o rede -g rede -m 644 "$f" "$PORTAL/$f"; done)
chmod 755 $PORTAL/agi/*.py
rm -rf /tmp/codigo-envio
echo "--- colunas novas"
# introspeccao como o usuario portal (so leitura), ALTER como postgres
SQL=$(cd $PORTAL && REDE_DATABASE_URL="$(grep '^REDE_DATABASE_URL=' /etc/rede-aberta/portal.env | cut -d= -f2- | tr -d '"')" \
  /opt/rede-aberta/venv/bin/python3 - <<'PY'
import os, sys
sys.path.insert(0, '/opt/rede-aberta/portal')
from rede import db
eng = db.criar_engine(os.environ['REDE_DATABASE_URL'])
for tabela, coluna, tipo in db.colunas_faltando(eng):
    print(f'ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {coluna} {tipo};')
PY
)
if [ -n "$SQL" ]; then echo "$SQL"; echo "$SQL" | sudo -u postgres psql -d telefone -v ON_ERROR_STOP=1 -q; else echo "nenhuma"; fi
systemctl restart rede-portal
systemctl is-active rede-grupo >/dev/null && systemctl restart rede-grupo || true
sleep 3
echo "--- servicos"; systemctl is-active rede-portal rede-grupo rede-jobs
curl -s -o /dev/null -w "portal: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar
journalctl -u rede-portal --since "-1 min" --no-pager -o cat | grep -iE "error|traceback" | tail -3 || true
REMOTO
echo "==> fim"
