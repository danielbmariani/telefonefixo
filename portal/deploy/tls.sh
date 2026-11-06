#!/usr/bin/env bash
# tls.sh — prepara a central para SIP por TLS (porta 5061) e SRTP. Rodar da maquina do operador:
#   deploy/tls.sh ~/.config/rede-aberta/bancada.env
# Le BANCADA_IP, BANCADA_SSH_KEY e, se existir, TLS_DOMINIO (padrao: telefonefixo.org). Usa a OCI CLI.
# O que faz (idempotente, SEM reiniciar o Asterisk e sem mexer em nenhum ramal):
#   1. copia o certificado Let's Encrypt do site para /etc/asterisk/keys (so o usuario asterisk le) e
#      instala o gancho do certbot que repete a copia e recarrega o PJSIP a cada renovacao
#   2. acrescenta [transport-tls] no pjsip.conf (mesmos enderecos externos do transport-tcp) e recarrega o PJSIP
#   3. libera TCP 5061 no iptables da maquina e num NSG da Oracle preso SO a esta maquina (a security list
#      da subnet e dividida com a VM antiga e nao e tocada)
#   4. confere o aperto de mao TLS de fora
# Os telefones so passam a usar TLS quando a linha muda de modo: flask sip-cifragem <ID|todas> <modo>.
# Ultimo passo, depois de todas as linhas estarem em modo exigida e registradas por TLS:
#   FECHAR_TCP=1 deploy/tls.sh   grava REDE_SIP_CIFRAGEM=exigida (linhas novas ja nascem cifradas), reinicia o
#                                portal e fecha a TCP 5060 no iptables (o tronco da operadora usa UDP e continua).
set -euo pipefail
ENVF="${1:-$HOME/.config/rede-aberta/bancada.env}"
set -a; . "$ENVF"; set +a
: "${BANCADA_IP:?}" "${BANCADA_SSH_KEY:?}"
DOMINIO="${TLS_DOMINIO:-telefonefixo.org}"
PORTA=5061
SSH_KEY="${BANCADA_SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "ubuntu@$BANCADA_IP")
export SUPPRESS_LABEL_WARNING=True

echo "==> 1 e 2. certificado, transporte TLS e iptables no servidor"
"${SSH[@]}" "sudo DOMINIO=$DOMINIO PORTA=$PORTA bash -s" <<'REMOTO'
set -euo pipefail
LE=/etc/letsencrypt/live/$DOMINIO
test -r $LE/fullchain.pem
GANCHO=/etc/letsencrypt/renewal-hooks/deploy/rede-asterisk-tls
cat > $GANCHO <<G
#!/bin/sh
# Copia o certificado renovado para o Asterisk (SIP por TLS) e recarrega o PJSIP. Instalado por deploy/tls.sh.
set -eu
install -d -m 750 -o asterisk -g asterisk /etc/asterisk/keys
install -m 640 -o asterisk -g asterisk $LE/fullchain.pem /etc/asterisk/keys/fullchain.pem
install -m 600 -o asterisk -g asterisk $LE/privkey.pem /etc/asterisk/keys/privkey.pem
asterisk -rx "module reload res_pjsip.so" >/dev/null 2>&1 || true
G
chmod 755 $GANCHO
antes=$(asterisk -rx "pjsip show contacts" | grep -c "Avail" || true)
if ! grep -q '^\[transport-tls\]' /etc/asterisk/pjsip.conf; then
  cp -p /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.conf.antes-tls
  # mesmos enderecos externos e rede local do transport-tcp
  extras=$(awk '/^\[transport-tcp\]/{f=1;next} /^\[|^#include/{f=0} f && /^(external_|local_net)/' /etc/asterisk/pjsip.conf)
  B=$(mktemp)
  printf '[transport-tls]\ntype = transport\nprotocol = tls\nbind = 0.0.0.0:%s\ncert_file = /etc/asterisk/keys/fullchain.pem\npriv_key_file = /etc/asterisk/keys/privkey.pem\nmethod = tlsv1_2\n%s\n\n' "$PORTA" "$extras" > "$B"
  awk -v f="$B" '/^#include pjsip_tronco.conf/ && !feito {while ((getline l < f) > 0) print l; feito=1} {print} END {if (!feito) {print ""; while ((getline l < f) > 0) print l}}' \
      /etc/asterisk/pjsip.conf.antes-tls > /etc/asterisk/pjsip.conf.novo
  install -m 640 -o asterisk -g asterisk /etc/asterisk/pjsip.conf.novo /etc/asterisk/pjsip.conf && rm -f /etc/asterisk/pjsip.conf.novo "$B"
  echo "    [transport-tls] acrescentado"
else
  echo "    [transport-tls] ja existia"
fi
$GANCHO
sleep 3
if ! iptables -C INPUT -p tcp -m tcp --dport $PORTA -j ACCEPT 2>/dev/null; then
  n=$(iptables -L INPUT --line-numbers -n | awk '/ACCEPT/ && /tcp dpt:5060/{print $1; exit}')
  iptables -I INPUT "${n:-1}" -p tcp -m tcp --dport $PORTA -j ACCEPT
  netfilter-persistent save >/dev/null 2>&1
  echo "    iptables: TCP $PORTA liberado"
fi
echo "--- transportes"; asterisk -rx "pjsip show transports" | awk '/^ *Transport:/ && !/<Trans/{print "    " $2, $3}'
depois=$(asterisk -rx "pjsip show contacts" | grep -c "Avail" || true)
echo "    telefones conectados: antes $antes, depois $depois"
ss -lnt | grep -q ":$PORTA " && echo "    escutando em $PORTA" || { echo "    NAO esta escutando em $PORTA: o transporte novo exige reiniciar o Asterisk (pedir autorizacao)"; exit 3; }
REMOTO

echo "==> 3. regra de rede na Oracle, so para esta maquina"
TENANCY=$(awk -F= '/^tenancy/{gsub(/ /,"",$2);print $2;exit}' ~/.oci/config)
INST=$(oci compute instance list --compartment-id "$TENANCY" --all --query 'data[?"lifecycle-state"==`RUNNING`].id' | python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin)))')
VNIC=""
for i in $INST; do
  v=$(oci compute instance list-vnics --instance-id "$i" --query "data[?\"public-ip\"=='$BANCADA_IP'].id | [0]" --raw-output 2>/dev/null || true)
  [ -n "$v" ] && [ "$v" != "None" ] && VNIC="$v"
done
test -n "$VNIC" || { echo "nao achei a VNIC desta maquina na Oracle"; exit 1; }
VCN=$(oci network vnic get --vnic-id "$VNIC" --query 'data."subnet-id"' --raw-output | xargs -I{} oci network subnet get --subnet-id {} --query 'data."vcn-id"' --raw-output)
NSG=$(oci network nsg list --compartment-id "$TENANCY" --vcn-id "$VCN" --display-name rede-aberta-sip-tls --query 'data[0].id' --raw-output 2>/dev/null || true)
if [ -z "$NSG" ] || [ "$NSG" = "None" ]; then
  NSG=$(oci network nsg create --compartment-id "$TENANCY" --vcn-id "$VCN" --display-name rede-aberta-sip-tls --query 'data.id' --raw-output)
  oci network nsg rules add --nsg-id "$NSG" --security-rules "[{\"direction\":\"INGRESS\",\"protocol\":\"6\",\"source\":\"0.0.0.0/0\",\"sourceType\":\"CIDR_BLOCK\",\"isStateless\":false,\"description\":\"SIP por TLS dos telefones\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":$PORTA,\"max\":$PORTA}}}]" >/dev/null
  echo "    NSG criado com TCP $PORTA"
else
  echo "    NSG ja existia"
fi
ATUAIS=$(oci network vnic get --vnic-id "$VNIC" --query 'data."nsg-ids"' 2>/dev/null || echo '[]')
NOVOS=$(python3 -c 'import json,sys; a=json.loads(sys.argv[1] or "[]") or []; n=sys.argv[2]; print(json.dumps(a if n in a else a+[n]))' "$ATUAIS" "$NSG")
if [ "$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1] or "[]") or []))' "$ATUAIS")" != "$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$NOVOS")" ]; then
  oci network vnic update --vnic-id "$VNIC" --nsg-ids "$NOVOS" --force >/dev/null
  echo "    NSG preso a esta maquina"
fi

echo "==> 4. aperto de mao TLS visto de fora"
sleep 5
openssl s_client -connect "$BANCADA_IP:$PORTA" -servername "$DOMINIO" </dev/null 2>/dev/null | openssl x509 -noout -subject -enddate 2>/dev/null | sed 's/^/    /' \
  || { echo "    sem resposta TLS em $PORTA"; exit 1; }
if [ "${FECHAR_TCP:-0}" = 1 ]; then
  echo "==> 5. linhas novas cifradas e porta TCP 5060 fechada"
  "${SSH[@]}" "sudo bash -s" <<'REMOTO'
set -euo pipefail
Q() { sudo -u postgres psql -d telefone -Atc "$1"; }
SEM=$(Q "select count(*) from criancas c join ps_endpoints e on e.id=c.id_rede where c.ativa and (e.media_encryption::text is distinct from 'sdes' or e.media_encryption_optimistic::text is distinct from 'no')")
TCP=$(Q "select count(*) from ps_contacts where uri ilike '%transport=tcp%'")
[ "$SEM" = 0 ] && [ "$TCP" = 0 ] || { echo "    ainda ha $SEM linha(s) fora do modo exigida e $TCP aparelho(s) registrado(s) por TCP; nada foi fechado"; exit 4; }
if grep -q '^REDE_SIP_CIFRAGEM=' /etc/rede-aberta/portal.env; then sed -i 's/^REDE_SIP_CIFRAGEM=.*/REDE_SIP_CIFRAGEM=exigida/' /etc/rede-aberta/portal.env
else echo 'REDE_SIP_CIFRAGEM=exigida' >> /etc/rede-aberta/portal.env; fi
systemctl restart rede-portal; sleep 3
curl -s -o /dev/null -w "    portal: HTTP %{http_code}\n" http://127.0.0.1:5000/entrar
while iptables -C INPUT -p tcp -m tcp --dport 5060 -j ACCEPT 2>/dev/null; do iptables -D INPUT -p tcp -m tcp --dport 5060 -j ACCEPT; done
netfilter-persistent save >/dev/null 2>&1
echo "    regras de entrada para SIP agora:"; iptables -S INPUT | grep -E -- "--dport (5060|5061) " | sed 's/^/      /'
REMOTO
  sleep 3
  if timeout 6 bash -c "exec 3<>/dev/tcp/$BANCADA_IP/5060" 2>/dev/null; then echo "    ATENCAO: TCP 5060 ainda responde de fora"; else echo "    de fora, TCP 5060 nao responde mais"; fi
fi
echo "==> fim"
