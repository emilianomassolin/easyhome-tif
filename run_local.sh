#!/usr/bin/env bash
# Inicia EasyHome completo en modo local.
# DB local: postgresql://easyhome_user:1234@localhost/easyhome
# Backend:  http://localhost:8000
# Frontend: http://localhost:5173

set -e
cd "$(dirname "$0")"

# ── PostgreSQL local ─────────────────────────────────────────────────────────
if ! pg_isready -q 2>/dev/null; then
    echo "[DB] Iniciando PostgreSQL local..."
    sudo systemctl start postgresql || true
fi
echo "[DB] PostgreSQL OK"

# ── FlareSolverr local (opcional, para scraping) ─────────────────────────────
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q flaresolverr-local; then
    echo "[FS] Iniciando FlareSolverr en puerto 8192..."
    docker run -d --name flaresolverr-local \
        -p 8192:8191 \
        ghcr.io/flaresolverr/flaresolverr:latest || true
fi
echo "[FS] FlareSolverr OK (puerto 8192)"

# ── Backend FastAPI ──────────────────────────────────────────────────────────
echo "[API] Iniciando backend en puerto 8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "[API] PID: $BACKEND_PID"

# ── Frontend Vite ────────────────────────────────────────────────────────────
echo "[FE] Iniciando frontend en puerto 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================="
echo " EasyHome corriendo en modo LOCAL"
echo "======================================="
echo " Frontend: http://localhost:5173"
echo " Backend:  http://localhost:8000"
echo " API docs: http://localhost:8000/docs"
echo " DB:       localhost/easyhome"
echo "======================================="
echo " Ctrl+C para detener todo"
echo ""

# Esperar a que alguno termine (o Ctrl+C)
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Detenido.'; exit" INT TERM
wait $BACKEND_PID $FRONTEND_PID
