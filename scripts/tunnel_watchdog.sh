#!/usr/bin/env bash
# Watchdog del quick-tunnel de Cloudflare. Verifica que el tunnel responda; si
# está caído (aunque cloudflared figure "active"), lo reinicia y propaga la URL
# nueva a vercel.json. Si responde pero la URL cambió, también la propaga.
# Corre como root vía systemd timer cada pocos minutos -> self-healing.
set -uo pipefail

LOG="/tmp/tunnel_watchdog.log"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

URL=$(journalctl -u cloudflared --no-pager 2>/dev/null \
  | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)

# ¿El tunnel responde de verdad?
if [ -n "$URL" ] && curl -s -o /dev/null --max-time 12 "$URL/api/health"; then
  # Sano: solo asegurar que vercel.json apunte a esta URL (el script es idempotente).
  /opt/easyhome/scripts/update_tunnel_url.sh >/dev/null 2>&1 || true
  exit 0
fi

# Túnel caído: reiniciar cloudflared para obtener una URL fresca y propagarla.
log "tunnel no responde ($URL) — reiniciando cloudflared"
systemctl restart cloudflared
sleep 15
/opt/easyhome/scripts/update_tunnel_url.sh >/dev/null 2>&1 || true
NEW=$(journalctl -u cloudflared --no-pager --since '40 seconds ago' 2>/dev/null \
  | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
log "cloudflared reiniciado -> URL nueva: ${NEW:-desconocida}"
