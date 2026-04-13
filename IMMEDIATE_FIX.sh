#!/bin/bash
# INSTRUÇÕES IMEDIATAS PARA CORRIGIR ERROR 502 NO HOST
# Execute estes comandos NO HOST onde o backend está rodando

echo "========================================="
echo "SMARTBLING 502 FIX - IMMEDIATE ACTION"
echo "========================================="
echo ""

# Step 1: Pull da correção
echo "[STEP 1/4] Pulling latest fixes from GitHub..."
cd /opt/smartB  # Ajustar para o caminho correto se diferente
git pull origin main

if [ $? -ne 0 ]; then
    echo "ERROR: git pull failed. Check internet and SSH key."
    exit 1
fi

echo "OK - Latest commits pulled"
echo ""

# Step 2: Ativar venv se necessário
echo "[STEP 2/4] Checking Python environment..."
if [ ! -d ".venv" ]; then
    echo "ERROR: .venv directory not found. Please create virtual environment first."
    exit 1
fi

source .venv/bin/activate
echo "OK - Virtual environment activated"
echo ""

# Step 3: Executar migration
echo "[STEP 3/4] Running Alembic migration..."
cd backend

# Verificar se alembic está disponível
if ! command -v alembic &> /dev/null; then
    echo "ERROR: alembic not found. Run: pip install alembic sqlalchemy"
    exit 1
fi

# Executar upgrade
alembic upgrade head

if [ $? -ne 0 ]; then
    echo "ERROR: Migration failed. Rolling back..."
    alembic downgrade -1
    exit 1
fi

echo "OK - Migration completed successfully"
echo ""

# Step 4: Reiniciar backend
echo "[STEP 4/4] Restarting backend service..."
cd ..

if systemctl is-active --quiet smartbling-backend; then
    sudo systemctl restart smartbling-backend
    echo "OK - Backend service restarted"
else
    echo "WARN - Service not found or not running. Manual restart may be needed."
fi

echo ""
echo "========================================="
echo "FIX COMPLETE"
echo "========================================="
echo ""
echo "Quick validation:"
echo "  1. Wait 5 seconds for backend to start..."
echo "  2. Try to access: http://localhost:8000/api/health"
echo "  3. Should see {'status': 'ok'} instead of 502"
echo ""
echo "If you see 502 error, check logs:"
echo "  sudo journalctl -u smartbling-backend -n 100"
echo ""
