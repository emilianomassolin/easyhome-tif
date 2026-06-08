#!/bin/bash
# Script de instalación para Oracle Cloud VM (Ubuntu 22.04 ARM)
# Correr como: bash deploy_oracle.sh

set -e
echo "=== EasyHome Deploy Script ==="

# 1. Dependencias del sistema
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip postgresql postgresql-contrib nginx git curl

# 2. Playwright dependencies
sudo apt install -y libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
  libatk-bridge2.0-0 libcups2 libdrm2 libxcb1 libxkbcommon0 libatspi2.0-0 \
  libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
  libgbm1 libpango-1.0-0 libcairo2 libasound2

# 3. PostgreSQL
sudo -u postgres psql -c "CREATE USER easyhome_user WITH PASSWORD '${DB_PASSWORD:-changeme}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE easyhome OWNER easyhome_user;" 2>/dev/null || true

# 4. Clonar repo (si no existe)
if [ ! -d "/opt/easyhome" ]; then
  sudo git clone https://github.com/TU_USUARIO/easyhome-tif.git /opt/easyhome
  sudo chown -R $USER:$USER /opt/easyhome
fi
cd /opt/easyhome

# 5. Entorno virtual Python
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

# 6. Archivo .env
cat > .env << EOF
DATABASE_URL=postgresql://easyhome_user:${DB_PASSWORD:-changeme}@localhost/easyhome
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
FACU_API_BASE=https://ai.cloud.um.edu.ar
FACU_API_KEY=${FACU_API_KEY}
FACU_MODEL=gemma4-e2b
ADMIN_TOKEN=${ADMIN_TOKEN:-admin-easyhome-2026}
JWT_SECRET=${JWT_SECRET:-change-this-secret}
ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-https://easyhome.vercel.app}
EOF

echo "=== Instalación completada ==="
echo "Iniciá el servidor con: .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000"
