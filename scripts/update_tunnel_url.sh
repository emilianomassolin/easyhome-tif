#!/usr/bin/env bash
# Mantiene frontend/vercel.json apuntando a la URL actual del quick-tunnel de
# cloudflared. El quick-tunnel cambia de URL en cada reinicio de cloudflared,
# así que esto se ejecuta al bootear Y periódicamente (systemd timer cada 5 min),
# y actualiza vercel.json vía la API de GitHub solo si la URL cambió.
#
# Requiere /opt/easyhome/.env.tunnel con:
#   GITHUB_TOKEN=ghp_...
#   GITHUB_REPO=usuario/repo
set -euo pipefail

ENV_FILE="/opt/easyhome/.env.tunnel"
LOG="/tmp/update_tunnel_url.log"
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

[ -f "$ENV_FILE" ] || { log "ERROR: falta $ENV_FILE"; exit 1; }
set -a; source "$ENV_FILE"; set +a

# URL del tunnel: buscar en TODO el journal (la línea aparece una sola vez al
# arrancar cloudflared; NO limitar con -n, se entierra bajo los logs de reintento).
TUNNEL_URL=""
for _ in $(seq 1 30); do
  TUNNEL_URL=$(journalctl -u cloudflared --no-pager 2>/dev/null \
    | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
  [ -n "$TUNNEL_URL" ] && break
  sleep 5
done
[ -n "$TUNNEL_URL" ] || { log "ERROR: no se pudo obtener la URL del tunnel"; exit 1; }

API="https://api.github.com/repos/$GITHUB_REPO/contents/frontend/vercel.json"
RESP=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$API")
SHA=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['sha'])")
CURRENT=$(echo "$RESP" | python3 -c "import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)['content']).decode())")

# Idempotente: si ya apunta a la URL actual, no commitear (el timer corre seguido).
if echo "$CURRENT" | grep -q "$TUNNEL_URL"; then
  exit 0
fi

NEW=$(printf '{\n  "rewrites": [\n    { "source": "/(.*)", "destination": "%s/$1" }\n  ]\n}\n' "$TUNNEL_URL")
ENC=$(echo "$NEW" | base64 -w0)
curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" -H "Content-Type: application/json" "$API" \
  -d "{\"message\":\"chore: update tunnel URL to $TUNNEL_URL\",\"content\":\"$ENC\",\"sha\":\"$SHA\"}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('commit',d['commit']['sha'][:12]) if d.get('commit') else sys.exit('fallo: '+str(d)[:200])" \
  && log "vercel.json actualizado a $TUNNEL_URL"
