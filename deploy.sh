#!/bin/bash
# Deploy completo: backend a VM + frontend vía git push (Vercel auto-deploy)
set -e

VM="ubuntu@10.201.3.235"
KEY="$HOME/.ssh/id_ed25519"
REMOTE="/opt/easyhome"

# ── 1. Backend → VM ──────────────────────────────────────────────────────────
echo "→ [Backend] Sincronizando archivos a la VM..."
rsync -az \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='node_modules' \
  --exclude='frontend/dist' \
  --exclude='.git' \
  --exclude='.env' \
  -e "ssh -i $KEY" \
  ./ "$VM:$REMOTE/"

echo "→ [Backend] Reiniciando servicio..."
ssh -i "$KEY" "$VM" "sudo systemctl restart easyhome"

echo "→ [Backend] Verificando..."
sleep 3
STATUS=$(ssh -i "$KEY" "$VM" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/health")
if [ "$STATUS" = "200" ]; then
  echo "  ✓ Backend OK (HTTP $STATUS)"
else
  echo "  ✗ Backend no responde (HTTP $STATUS)"
  ssh -i "$KEY" "$VM" "sudo journalctl -u easyhome --no-pager -n 20"
  exit 1
fi

# ── 2. Frontend → GitHub → Vercel ────────────────────────────────────────────
if [ -n "$(git status --porcelain)" ]; then
  echo "→ [Frontend] Hay cambios sin commitear, hacé commit antes de hacer deploy."
  git status --short
  exit 1
fi

UNPUSHED=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNPUSHED" = "0" ]; then
  echo "→ [Frontend] Sin commits nuevos para pushear."
else
  echo "→ [Frontend] Pusheando $UNPUSHED commit(s) a GitHub (Vercel auto-deploy)..."
  git push origin main
  echo "  ✓ Push OK — Vercel va a buildear y deployar el frontend automáticamente"
  echo "  Ver estado: https://vercel.com/dashboard"
fi

echo ""
echo "✓ Deploy completado"
