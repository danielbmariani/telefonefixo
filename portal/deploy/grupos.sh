#!/usr/bin/env bash
# grupos.sh — instala/atualiza a chamada em grupo (doc 16) no servidor da bancada.
#   deploy/grupos.sh ~/.config/rede-aberta/bancada.env
# Le BANCADA_IP e BANCADA_SSH_KEY. O que faz, por SSH, como root:
#   1. envia o codigo do portal (rede/, agi/, deploy/) e instala como usuario rede
#   2. cria as tabelas grupos e grupo_membros (como postgres) e ajusta grants
#   3. websockets no venv; tenta instalar o piper (voz natural pt-BR) e o modelo; senao fica o espeak-ng
#   4. gera as frases fixas, os tons, o tom de chamando e os apelidos/grupos que ainda nao tem audio
#   5. ARI e HTTP do Asterisk em localhost (senha gerada aqui, nunca impressa), musica de espera, dialplan
#   6. servico rede-grupo (systemd), reinicio do Asterisk e do portal, verificacao
# Idempotente. Nunca imprime senhas.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Empacotando codigo"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar -C "$AQUI" -czf "$TMP/codigo.tgz" --exclude='__pycache__' --exclude='*.pyc' --exclude='rede-dev.db' \
    rede agi deploy/asterisk deploy/rede-grupo.service requirements.txt wsgi.py

echo "==> Enviando"
"${SSH[@]}" "sudo rm -rf /tmp/grupos-envio && mkdir -p /tmp/grupos-envio && chmod 700 /tmp/grupos-envio"
scp -i "$SSH_KEY" -q "$TMP/codigo.tgz" "ubuntu@$BANCADA_IP:/tmp/grupos-envio/"

"${SSH[@]}" "sudo bash -s" <<'REMOTO'
set -euo pipefail
PORTAL=/opt/rede-aberta/portal; VENV=/opt/rede-aberta/venv; ENVP=/etc/rede-aberta/portal.env
SONS=/var/lib/rede-aberta/sons; PIPER_DIR=/opt/rede-aberta/piper
echo "[1/6] codigo"
mkdir -p /tmp/grupos-envio/src && tar -C /tmp/grupos-envio/src -xzf /tmp/grupos-envio/codigo.tgz
(cd /tmp/grupos-envio/src && find . -type f | while read -r f; do install -D -o rede -g rede -m 644 "$f" "$PORTAL/$f"; done)
chmod 755 $PORTAL/agi/*.py
for f in $PORTAL/agi/*.py; do ln -sf "$f" /usr/share/asterisk/agi-bin/; done
rm -f /usr/share/asterisk/agi-bin/check_group.py /usr/share/asterisk/agi-bin/conf_leave.py $PORTAL/agi/check_group.py $PORTAL/agi/conf_leave.py $PORTAL/rede/templates/_id.html 2>/dev/null || true

echo "[2/6] banco"
sudo -u postgres psql -d telefone -q <<SQL
CREATE TABLE IF NOT EXISTS grupos (
  id SERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  crianca_dona_id INTEGER NOT NULL REFERENCES criancas(id),
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE TABLE IF NOT EXISTS grupo_membros (
  id SERIAL PRIMARY KEY,
  grupo_id INTEGER NOT NULL REFERENCES grupos(id),
  crianca_id INTEGER NOT NULL REFERENCES criancas(id),
  codigo INTEGER NOT NULL,
  entrou_em TIMESTAMP WITH TIME ZONE NOT NULL,
  saiu_em TIMESTAMP WITH TIME ZONE,
  CONSTRAINT grupo_membro_unico UNIQUE (grupo_id, crianca_id)
);
CREATE INDEX IF NOT EXISTS grupo_membros_crianca ON grupo_membros (crianca_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO portal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO portal;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log, device_state_history, prov_log, gdms_log FROM portal;
SQL

echo "[3/6] dependencias: websockets; piper (opcional)"
sudo -u rede $VENV/bin/pip install -q 'websockets>=12,<15' 2>&1 | grep -v "^$" | tail -2 || true
mkdir -p $PIPER_DIR; chown rede:rede $PIPER_DIR
if ! sudo -u rede $VENV/bin/python -c "import piper" 2>/dev/null; then
  sudo -u rede $VENV/bin/pip install -q piper-tts 2>&1 | tail -1 || echo "aviso: piper nao instalou (fica o espeak-ng)"
fi
if [ ! -f $PIPER_DIR/pt_BR-faber-medium.onnx ]; then
  B=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium
  (sudo -u rede curl -fsSL "$B/pt_BR-faber-medium.onnx" -o $PIPER_DIR/pt_BR-faber-medium.onnx \
   && sudo -u rede curl -fsSL "$B/pt_BR-faber-medium.onnx.json" -o $PIPER_DIR/pt_BR-faber-medium.onnx.json) \
   || { echo "aviso: modelo do piper nao baixou (fica o espeak-ng)"; rm -f $PIPER_DIR/pt_BR-faber-medium.onnx; }
fi
ln -sf $VENV/bin/piper /usr/local/bin/piper 2>/dev/null || true

echo "[4/6] portal.env e sons"
grep -q '^REDE_VOZ_BACKEND=' $ENVP || echo "REDE_VOZ_BACKEND=auto" >> $ENVP
grep -q '^REDE_VOZ_DIR=' $ENVP || echo "REDE_VOZ_DIR=$SONS" >> $ENVP
grep -q '^REDE_VOZ_PIPER_MODELO=' $ENVP || echo "REDE_VOZ_PIPER_MODELO=$PIPER_DIR/pt_BR-faber-medium.onnx" >> $ENVP
grep -q '^REDE_ARI_URL=' $ENVP || echo "REDE_ARI_URL=http://127.0.0.1:8088/ari" >> $ENVP
grep -q '^REDE_ARI_USUARIO=' $ENVP || echo "REDE_ARI_USUARIO=rede" >> $ENVP
if ! grep -q '^REDE_ARI_SENHA=' $ENVP; then
  echo "REDE_ARI_SENHA=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)" >> $ENVP
fi
grep -q '^REDE_GRUPO_MAX_NA_CHAMADA=' $ENVP || echo "REDE_GRUPO_MAX_NA_CHAMADA=4" >> $ENVP
mkdir -p $SONS; chown rede:rede $SONS; chmod 755 $SONS
ln -sfn $SONS /usr/share/asterisk/sounds/rede
# frases, tons e apelidos/grupos que ainda nao tem audio, como usuario rede (le o portal.env)
sudo -u rede env $(grep -v '^#' $ENVP | xargs) $VENV/bin/python - <<'PY'
import os
from rede import db, voz
from rede.config import Config
from sqlalchemy import select
cfg = Config()
print('voz:', voz.backend_disponivel(cfg) or 'nenhuma', '| frases gravadas:', voz.gerar_frases(cfg), '| tons:', voz.gerar_tons(cfg))
eng = db.criar_engine(cfg.DATABASE_URL)
n = 0
with eng.begin() as conn:
    for c in conn.execute(select(db.criancas.c.id_rede, db.criancas.c.apelido).where(db.criancas.c.ativa.is_(True))).all():
        if not voz.tem_apelido(cfg, c.id_rede) and voz.gerar_apelido(cfg, c.id_rede, c.apelido):
            n += 1
    for g in conn.execute(select(db.grupos.c.id, db.grupos.c.nome).where(db.grupos.c.ativo.is_(True))).all():
        if not voz.tem_grupo(cfg, g.id):
            voz.gerar_grupo(cfg, g.id, g.nome)
print('apelidos gravados agora:', n)
PY
chmod -R a+rX $SONS

echo "[5/6] asterisk: ARI, HTTP, musica de espera, dialplan"
ARI_SENHA=$(grep '^REDE_ARI_SENHA=' $ENVP | cut -d= -f2-)
sed "s|TROCAR_SENHA|$ARI_SENHA|" $PORTAL/deploy/asterisk/ari.conf > /etc/asterisk/ari.conf
chown asterisk:asterisk /etc/asterisk/ari.conf; chmod 640 /etc/asterisk/ari.conf
install -o asterisk -g asterisk -m 640 $PORTAL/deploy/asterisk/http.conf /etc/asterisk/http.conf
install -o asterisk -g asterisk -m 640 $PORTAL/deploy/asterisk/musiconhold-rede.conf /etc/asterisk/musiconhold-rede.conf
grep -q '^#include musiconhold-rede.conf' /etc/asterisk/musiconhold.conf 2>/dev/null || printf '\n#include musiconhold-rede.conf\n' >> /etc/asterisk/musiconhold.conf
install -o asterisk -g asterisk -m 640 $PORTAL/deploy/asterisk/extensions.conf /etc/asterisk/extensions.conf
rm -f /etc/asterisk/confbridge.conf.rede 2>/dev/null || true
for m in res_http_websocket res_stasis res_ari res_ari_events res_ari_channels res_ari_bridges res_ari_playbacks res_ari_asterisk res_stasis_playback res_stasis_answer res_stasis_snoop res_stasis_recording res_stasis_device_state app_stasis; do
  sed -i "/^noload = $m.so/d" /etc/asterisk/modules.conf
done

echo "[6/6] servico rede-grupo e reinicios"
install -m 644 $PORTAL/deploy/rede-grupo.service /etc/systemd/system/rede-grupo.service
systemctl daemon-reload
systemctl restart asterisk
sleep 4
systemctl enable --now rede-grupo.service >/dev/null
systemctl restart rede-portal
sleep 3
rm -rf /tmp/grupos-envio
echo "--- servicos"; systemctl is-active asterisk rede-grupo rede-portal
echo "--- ARI"; asterisk -rx "ari show apps" | head -5; asterisk -rx "ari show users" | head -5
echo "--- dialplan"; asterisk -rx "dialplan show _0[1-9]@telefones-criancas" | head -8
echo "--- sons"; ls /usr/share/asterisk/sounds/rede/frases | wc -l; ls /usr/share/asterisk/sounds/rede/apelidos 2>/dev/null | wc -l
echo "--- rede-grupo"; journalctl -u rede-grupo --since "-1 min" --no-pager -o cat | tail -5
echo "--- erros asterisk"; journalctl -u asterisk --since "-2 min" --no-pager 2>/dev/null | grep -iE "error|warning" | grep -iv "deprecat" | tail -5 || true
curl -s -o /dev/null -w "portal: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar
REMOTO
echo "==> fim"
