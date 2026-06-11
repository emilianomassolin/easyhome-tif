#!/bin/bash
# Deploy completo: backend a VM + frontend dist a VM + script de tunnel + git push (Vercel)
set -e

VM="ubuntu@10.201.3.235"
KEY="$HOME/.ssh/id_ed25519"
REMOTE="/opt/easyhome"
SSH="ssh -i $KEY"

# ── 1. Build frontend ─────────────────────────────────────────────────────────
echo "→ [Frontend] Construyendo..."
(cd frontend && npm run build)
echo "  ✓ Build OK"

# ── 2. Backend → VM ──────────────────────────────────────────────────────────
echo "→ [Backend] Sincronizando archivos a la VM..."
rsync -az \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='.env' \
  -e "ssh -i $KEY" \
  ./ "$VM:$REMOTE/"

# ── 3. Frontend dist → VM ─────────────────────────────────────────────────────
echo "→ [Frontend] Copiando dist a la VM..."
rsync -az -e "ssh -i $KEY" frontend/dist/ "$VM:$REMOTE/frontend/dist/"
echo "  ✓ dist copiado"

# ── 4. Instalar script de tunnel en VM ────────────────────────────────────────
echo "→ [Tunnel] Instalando script de actualización automática..."
$SSH "$VM" "chmod +x $REMOTE/scripts/update_tunnel_url.sh"
$SSH "$VM" "sudo cp $REMOTE/scripts/update-tunnel-url.service /etc/systemd/system/"
$SSH "$VM" "sudo systemctl daemon-reload && sudo systemctl enable update-tunnel-url.service"
echo "  ✓ Servicio de tunnel instalado"

# ── 5. Reiniciar backend ──────────────────────────────────────────────────────
echo "→ [Backend] Reiniciando servicio..."
$SSH "$VM" "sudo systemctl restart easyhome"

echo "→ [Backend] Verificando..."
sleep 3
STATUS=$($SSH "$VM" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/health")
if [ "$STATUS" = "200" ]; then
  echo "  ✓ Backend OK (HTTP $STATUS)"
else
  echo "  ✗ Backend no responde (HTTP $STATUS)"
  $SSH "$VM" "sudo journalctl -u easyhome --no-pager -n 20"
  exit 1
fi

# ── 6. Frontend → GitHub → Vercel ────────────────────────────────────────────
if [ -n "$(git status --porcelain)" ]; then
  echo "→ [Git] Hay cambios sin commitear, hacé commit antes de hacer deploy."
  git status --short
  exit 1
fi

UNPUSHED=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNPUSHED" = "0" ]; then
  echo "→ [Git] Sin commits nuevos para pushear."
else
  echo "→ [Git] Pusheando $UNPUSHED commit(s) a GitHub (Vercel auto-deploy)..."
  git push origin main
  echo "  ✓ Push OK — Vercel va a buildear y deployar el frontend automáticamente"
  echo "  Ver estado: https://vercel.com/dashboard"
fi

echo ""
echo "✓ Deploy completado"
echo ""
echo "IMPORTANTE: Si el tunnel de la VM acaba de arrancar, el vercel.json"
echo "se actualiza automáticamente vía el servicio 'update-tunnel-url'."
echo "Si querés forzar la actualización ahora:"
echo "  ssh -i $KEY $VM 'sudo systemctl start update-tunnel-url'"
