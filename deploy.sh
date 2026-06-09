#!/bin/bash
# Sincroniza cambios locales a la VM de la facu y reinicia el backend
set -e

VM="ubuntu@10.201.3.235"
KEY="$HOME/.ssh/id_ed25519"
REMOTE="/opt/easyhome"

echo "→ Sincronizando archivos..."
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

echo "→ Reiniciando backend..."
ssh -i "$KEY" "$VM" "sudo systemctl restart easyhome"

echo "→ Verificando..."
sleep 2
ssh -i "$KEY" "$VM" "curl -s http://localhost:8000/api/health"

echo ""
echo "✓ Deploy completado"
