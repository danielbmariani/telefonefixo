#!/usr/bin/env bash
# tronco.sh — instala/atualiza o tronco da operadora (B23) no servidor da bancada.
#   deploy/tronco.sh ~/.config/rede-aberta/bancada.env
# Le TRONCO_SERVIDOR, TRONCO_USUARIO, TRONCO_SENHA, TRONCO_NUMERO, ALERTA_EMAIL (e BANCADA_IP, BANCADA_SSH_KEY).
# O que faz, por SSH, como root:
#   1. envia o codigo do portal (rede/, agi/, deploy/asterisk/) e instala como usuario rede
#   2. cria a tabela familia_telefones (flask init-db) e ajusta dono/grants
#   3. grava /etc/asterisk/pjsip_tronco.conf (senha so no servidor, 640 asterisk) e o #include
#   4. copia extensions.conf e sorcery.conf, linka o AGI check_entrada.py, gera o som sem-celular
#   5. REDE_TRONCO_NUMERO no portal.env, reinicia portal e Asterisk, mostra o registro no tronco
# Nunca imprime a senha. Idempotente.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}" "${TRONCO_SERVIDOR:?}" "${TRONCO_USUARIO:?}" "${TRONCO_SENHA:?}" "${TRONCO_NUMERO:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Empacotando codigo"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -C "$AQUI" -czf "$TMP/codigo.tgz" --exclude='__pycache__' --exclude='*.pyc' --exclude='rede-dev.db' \
    rede agi deploy/asterisk deploy/rede-portal.service deploy/rede-jobs.service deploy/retencao.sql deploy/rede-retencao.cron deploy/logrotate-nginx-rede requirements.txt wsgi.py
sed -e "s|__SERVIDOR__|$TRONCO_SERVIDOR|g" -e "s|__USUARIO__|$TRONCO_USUARIO|g" -e "s|__SENHA__|$TRONCO_SENHA|g" \
    "$AQUI/deploy/asterisk/pjsip_tronco.conf.exemplo" > "$TMP/pjsip_tronco.conf"

echo "==> Enviando"
"${SSH[@]}" "sudo rm -rf /tmp/tronco-envio && mkdir -p /tmp/tronco-envio && chmod 700 /tmp/tronco-envio"
scp -i "$SSH_KEY" -q "$TMP/codigo.tgz" "$TMP/pjsip_tronco.conf" "ubuntu@$BANCADA_IP:/tmp/tronco-envio/"

"${SSH[@]}" "sudo env TRONCO_NUMERO='$TRONCO_NUMERO' ALERTA_EMAIL='${ALERTA_EMAIL:-}' bash -s" <<'REMOTO'
set -euo pipefail
PORTAL=/opt/rede-aberta/portal; VENV=/opt/rede-aberta/venv; ENVP=/etc/rede-aberta/portal.env
echo "[1/5] codigo"
mkdir -p /tmp/tronco-envio/src && tar -C /tmp/tronco-envio/src -xzf /tmp/tronco-envio/codigo.tgz
(cd /tmp/tronco-envio/src && find . -type f | while read -r f; do install -D -o rede -g rede -m 644 "$f" "$PORTAL/$f"; done)
chmod 755 $PORTAL/agi/*.py
for f in $PORTAL/agi/*.py; do ln -sf "$f" /usr/share/asterisk/agi-bin/; done
echo "[2/5] banco"
# Tabelas novas sao criadas como postgres (o papel portal nao tem REFERENCES nas tabelas existentes).
sudo -u postgres psql -d telefone -q <<SQL
CREATE TABLE IF NOT EXISTS familia_telefones (
  id SERIAL PRIMARY KEY,
  familia_id INTEGER NOT NULL REFERENCES familias(id) ON DELETE CASCADE,
  numero TEXT NOT NULL,
  apelido TEXT NOT NULL DEFAULT '',
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em TIMESTAMP WITH TIME ZONE NOT NULL,
  verificado_em TIMESTAMP WITH TIME ZONE,
  CONSTRAINT familia_telefones_unico UNIQUE (familia_id, numero)
);
CREATE INDEX IF NOT EXISTS familia_telefones_numero ON familia_telefones (numero);
ALTER TABLE familia_telefones ADD COLUMN IF NOT EXISTS posicao INTEGER;
UPDATE familia_telefones t SET posicao = s.rn FROM (
  SELECT id, row_number() OVER (PARTITION BY familia_id ORDER BY id) AS rn FROM familia_telefones WHERE ativo) s
  WHERE t.id = s.id AND t.posicao IS NULL AND s.rn <= 2;
CREATE TABLE IF NOT EXISTS chamadas_resumo (
  dia TEXT PRIMARY KEY,
  chamadas INTEGER NOT NULL DEFAULT 0,
  segundos INTEGER NOT NULL DEFAULT 0,
  bloqueadas INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alertas_custo (chave TEXT PRIMARY KEY, ts TIMESTAMP WITH TIME ZONE NOT NULL);
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO portal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO portal;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log, device_state_history, prov_log, gdms_log FROM portal;
SQL
echo "[3/5] pjsip_tronco.conf"
install -o asterisk -g asterisk -m 640 /tmp/tronco-envio/pjsip_tronco.conf /etc/asterisk/pjsip_tronco.conf
grep -q '^#include pjsip_tronco.conf' /etc/asterisk/pjsip.conf || printf '\n#include pjsip_tronco.conf\n' >> /etc/asterisk/pjsip.conf
echo "[4/5] dialplan, sorcery, som"
install -o asterisk -g asterisk -m 640 $PORTAL/deploy/asterisk/extensions.conf /etc/asterisk/extensions.conf
install -o asterisk -g asterisk -m 640 $PORTAL/deploy/asterisk/sorcery.conf /etc/asterisk/sorcery.conf
if [ ! -f /usr/share/asterisk/sounds/telefone/sem-minutos.wav ]; then
  espeak-ng -v pt-br -s 140 -w /tmp/sm.wav "Os minutos para celular deste mês acabaram. Volta no mês que vem." 2>/dev/null \
    && sox /tmp/sm.wav -r 8000 -c 1 -b 16 /usr/share/asterisk/sounds/telefone/sem-minutos.wav \
    && chown asterisk:asterisk /usr/share/asterisk/sounds/telefone/sem-minutos.wav || echo "aviso: som sem-minutos nao gerado"
fi
if [ ! -f /usr/share/asterisk/sounds/telefone/sem-celular.wav ]; then
  espeak-ng -v pt-br -s 140 -w /tmp/sc.wav "O celular da família ainda não foi cadastrado no site." 2>/dev/null \
    && sox /tmp/sc.wav -r 8000 -c 1 -b 16 /usr/share/asterisk/sounds/telefone/sem-celular.wav \
    && chown asterisk:asterisk /usr/share/asterisk/sounds/telefone/sem-celular.wav || echo "aviso: som sem-celular nao gerado"
fi
echo "[5/5] retencao, logrotate, portal.env e reinicio"
install -m 644 $PORTAL/deploy/rede-retencao.cron /etc/cron.d/rede-retencao
install -m 644 $PORTAL/deploy/logrotate-nginx-rede /etc/logrotate.d/nginx-rede
install -m 644 $PORTAL/deploy/retencao.sql /etc/rede-aberta/retencao.sql   # legivel pelo postgres
mkdir -p /var/log/rede-aberta; touch /var/log/rede-aberta/retencao.log
sudo -u postgres psql -d telefone -q -f /etc/rede-aberta/retencao.sql && echo "retencao.sql ok"
[ -n "${ALERTA_EMAIL:-}" ] && { grep -q '^REDE_ALERTA_EMAIL=' $ENVP || echo "REDE_ALERTA_EMAIL=$ALERTA_EMAIL" >> $ENVP; }
if grep -q '^REDE_TRONCO_NUMERO=' $ENVP; then sed -i "s|^REDE_TRONCO_NUMERO=.*|REDE_TRONCO_NUMERO=$TRONCO_NUMERO|" $ENVP; else echo "REDE_TRONCO_NUMERO=$TRONCO_NUMERO" >> $ENVP; fi
systemctl restart rede-portal
# sorcery.conf so e lido na carga do modulo: reinicio completo do Asterisk (os GRP re-registram em ate 1 min)
systemctl restart asterisk
sleep 4
rm -rf /tmp/tronco-envio
echo "--- registro no tronco"; asterisk -rx "pjsip show registrations"
echo "--- endpoint"; asterisk -rx "pjsip show endpoint nvoip" | grep -E "Endpoint:|Contact:|Identify|match" | head
echo "--- dialplan"; asterisk -rx "dialplan show tronco-entrada" | head -5
echo "--- erros recentes"; journalctl -u asterisk --since "-2 min" --no-pager 2>/dev/null | grep -iE "error|warning" | grep -iv "deprecat" | tail -5 || true
curl -s -o /dev/null -w "portal: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar
REMOTO
echo "==> FIM. Acompanhe: ssh ... sudo asterisk -rvvv"
