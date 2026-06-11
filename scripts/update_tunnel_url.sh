#!/usr/bin/env bash
# Ejecutado por systemd al iniciar la VM.
# Espera que cloudflared obtenga su URL, la extrae,
# y actualiza vercel.json en GitHub para que Vercel redeploy automáticamente.
#
# Requiere: GITHUB_TOKEN en /opt/easyhome/.env.tunnel
# Formato de /opt/easyhome/.env.tunnel:
#   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
#   GITHUB_REPO=emilianomassolin/easyhome-tif

set -euo pipefail

ENV_FILE="/opt/easyhome/.env.tunnel"
LOG="/tmp/update_tunnel_url.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

if [ ! -f "$ENV_FILE" ]; then
  log "ERROR: $ENV_FILE no existe. Crealo con GITHUB_TOKEN y GITHUB_REPO."
  exit 1
fi

source "$ENV_FILE"

log "Esperando URL de cloudflared..."
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(journalctl -u cloudflared --no-pager -n 500 2>/dev/null \
    | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
  if [ -n "$TUNNEL_URL" ]; then
    break
  fi
  sleep 5
done

if [ -z "$TUNNEL_URL" ]; then
  log "ERROR: No se pudo obtener la URL del tunnel después de 150s."
  exit 1
fi

log "URL del tunnel: $TUNNEL_URL"

# Obtener el archivo actual de GitHub (necesitamos el SHA para actualizarlo)
RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO/contents/frontend/vercel.json")

SHA=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")

NEW_CONTENT=$(printf '{\n  "rewrites": [\n    { "source": "/(.*)", "destination": "%s/$1" }\n  ]\n}\n' "$TUNNEL_URL")
ENCODED=$(echo "$NEW_CONTENT" | base64 -w 0)

# Actualizar en GitHub
UPDATE=$(curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/$GITHUB_REPO/contents/frontend/vercel.json" \
  -d "{\"message\":\"chore: update tunnel URL to $TUNNEL_URL\",\"content\":\"$ENCODED\",\"sha\":\"$SHA\"}")

if echo "$UPDATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit',{}).get('sha',''))" 2>/dev/null | grep -q .; then
  log "vercel.json actualizado correctamente. Vercel va a redesplegar en ~2 min."
else
  log "ERROR actualizando GitHub: $UPDATE"
  exit 1
fi
