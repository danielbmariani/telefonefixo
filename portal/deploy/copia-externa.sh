#!/usr/bin/env bash
# copia-externa.sh — copia diaria do banco FORA do servidor (doc 14). Rodar da maquina do operador:
#   deploy/copia-externa.sh ~/.config/rede-aberta/bancada.env
# Precisa da OCI CLI configurada (~/.oci/config) e de gpg. Le BANCADA_IP e BANCADA_SSH_KEY.
# O que faz (idempotente):
#   1. cria, so nesta maquina, o par de chaves que cifra as copias (~/.config/rede-aberta/copia-gpg).
#      A chave privada NUNCA vai para o servidor nem para o repositorio. Sem ela a copia externa nao abre:
#      guarde tambem num gerenciador de senhas (gpg --homedir ... --armor --export-secret-keys).
#   2. cria o bucket privado na mesma regiao do servidor (os dados nao saem da Oracle em Sao Paulo)
#   3. regra do bucket: objeto com mais de 14 dias e apagado (mesmo prazo da politica de privacidade)
#   4. cria um endereco que so aceita gravacao (pre-authenticated request) e grava no servidor em
#      /etc/rede-aberta/copia.env (600 root). O endereco e segredo e nunca e impresso.
#   5. instala a chave publica e o rede-backup-db novo, roda uma copia e confere que ela chegou e abre.
# Restaurar: ver deploy/README.md, secao Backup.
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
AQUI="$(cd "$(dirname "$0")" && pwd)"
BUCKET="${COPIA_BUCKET:-telefone-fixo-copias}"
DIAS=14
CHAVES="$HOME/.config/rede-aberta/copia-gpg"
export SUPPRESS_LABEL_WARNING=True
TENANCY=$(awk -F= '/^tenancy/{gsub(/ /,"",$2);print $2;exit}' ~/.oci/config)
REGIAO=$(awk -F= '/^region/{gsub(/ /,"",$2);print $2;exit}' ~/.oci/config)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "==> 1. chave de cifragem (so nesta maquina)"
if [ ! -d "$CHAVES" ]; then
  mkdir -m 700 "$CHAVES"
  gpg --homedir "$CHAVES" --batch --quiet --pinentry-mode loopback --passphrase '' --quick-generate-key "Telefone Fixo copia de seguranca" default default never
  echo "    criada em $CHAVES"
else
  echo "    ja existe em $CHAVES"
fi
gpg --homedir "$CHAVES" --batch --quiet --armor --export > "$TMP/copia-pub.asc"
test -s "$TMP/copia-pub.asc"

echo "==> 2. bucket $BUCKET em $REGIAO"
if oci os bucket get --bucket-name "$BUCKET" >/dev/null 2>&1; then
  echo "    ja existe"
else
  oci os bucket create --compartment-id "$TENANCY" --name "$BUCKET" --public-access-type NoPublicAccess --versioning Disabled >/dev/null
  echo "    criado (privado)"
fi

echo "==> 3. apagar copias com mais de $DIAS dias"
if ! oci iam policy list --compartment-id "$TENANCY" --all --query "data[?name=='copias-ciclo-de-vida'] | length(@)" --raw-output | grep -q '^1$'; then
  oci iam policy create --compartment-id "$TENANCY" --name copias-ciclo-de-vida \
    --description "Deixa o Object Storage apagar copias vencidas do bucket $BUCKET" \
    --statements "[\"Allow service objectstorage-$REGIAO to manage object-family in tenancy where target.bucket.name='$BUCKET'\"]" >/dev/null
  echo "    politica criada; esperando propagar"; sleep 20
fi
REGRA="[{\"name\":\"apagar-apos-$DIAS-dias\",\"action\":\"DELETE\",\"timeAmount\":$DIAS,\"timeUnit\":\"DAYS\",\"isEnabled\":true,\"target\":\"objects\"}]"
for tentativa in 1 2 3 4 5 6; do   # a politica nova pode levar um ou dois minutos para valer
  oci os object-lifecycle-policy put --bucket-name "$BUCKET" --force --items "$REGRA" >/dev/null 2>"$TMP/regra.err" && break
  [ "$tentativa" = 6 ] && { cat "$TMP/regra.err"; exit 1; }
  sleep 20
done
echo "    regra ativa"

echo "==> 4. endereco de gravacao no servidor"
if "${SSH[@]}" "sudo test -s /etc/rede-aberta/copia.env" && [ "${NOVO_ENDERECO:-0}" != 1 ]; then
  echo "    ja configurado (NOVO_ENDERECO=1 para trocar)"
  URL=""
else
  oci os preauth-request create --bucket-name "$BUCKET" --name "servidor-$(date +%Y%m%d-%H%M)" \
    --access-type AnyObjectWrite --time-expires 2036-01-01T00:00:00Z > "$TMP/par.json"
  URL=$(python3 - "$TMP/par.json" "$REGIAO" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))['data']
print(d.get('full-path') or f"https://objectstorage.{sys.argv[2]}.oraclecloud.com{d['access-uri']}")
PY
)
  rm -f "$TMP/par.json"
  echo "    criado (validade ate 2036; o aviso diario acusa se parar de funcionar)"
fi

echo "==> 5. instalando no servidor e fazendo a primeira copia"
"${SSH[@]}" "sudo rm -rf /tmp/copia-envio && mkdir -m 700 /tmp/copia-envio"
scp -i "$SSH_KEY" -q "$TMP/copia-pub.asc" "$AQUI/seguranca/rede-backup-db" "ubuntu@$BANCADA_IP:/tmp/copia-envio/"
# o endereco vai pela entrada padrao do ssh, nunca pela linha de comando
printf '%s\n' "$URL" | "${SSH[@]}" "sudo bash -c '
set -euo pipefail
read -r URL || true
install -m 644 -o root -g root /tmp/copia-envio/copia-pub.asc /etc/rede-aberta/copia-pub.asc
install -m 755 /tmp/copia-envio/rede-backup-db /usr/local/sbin/rede-backup-db
if [ -n \"\$URL\" ]; then umask 077; printf \"COPIA_URL=%s\n\" \"\$URL\" > /etc/rede-aberta/copia.env; chown root:root /etc/rede-aberta/copia.env; chmod 600 /etc/rede-aberta/copia.env; fi
grep -q \"^REDE_COPIA_EXTERNA_STATUS=\" /etc/rede-aberta/portal.env || echo \"REDE_COPIA_EXTERNA_STATUS=/var/backups/rede-aberta/copia-externa.ok\" >> /etc/rede-aberta/portal.env
rm -rf /tmp/copia-envio
/usr/local/sbin/rede-backup-db && tail -2 /var/log/rede-aberta/backup.log
'"

echo "==> conferindo no bucket (nome, tamanho) e abrindo a copia mais nova sem gravar nada em disco"
oci os object list --bucket-name "$BUCKET" --all --query 'data[].{nome:name,bytes:size}' --output table | tail -6
ULTIMO=$(oci os object list --bucket-name "$BUCKET" --all --query 'sort_by(data, &"time-created")[-1].name' --raw-output)
set +o pipefail   # o head fecha o cano cedo de proposito
oci os object get --bucket-name "$BUCKET" --name "$ULTIMO" --file - 2>/dev/null \
  | gpg --homedir "$CHAVES" --batch --quiet --decrypt 2>/dev/null | gunzip 2>/dev/null | head -c 400 | grep -c "PostgreSQL database dump" \
  | sed 's/^1$/    a copia abre com a chave local: ok/; s/^0$/    ERRO: a copia nao abriu/'
echo "==> fim"
