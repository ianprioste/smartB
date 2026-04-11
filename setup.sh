#!/bin/bash

# Script de inicialização do SmartBling

echo "==================================="
echo "SmartBling - Inicializador"
echo "==================================="
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar Python
echo -e "${YELLOW}Verificando Python...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}Python não encontrado. Instale Python 3.8+${NC}"
    exit 1
fi
echo -e "${GREEN}Python encontrado${NC}"

# Verificar Node.js
echo -e "${YELLOW}Verificando Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js não encontrado. Instale Node.js 16+${NC}"
    exit 1
fi
echo -e "${GREEN}Node.js encontrado${NC}"

# Backend
echo ""
echo -e "${YELLOW}Configurando Backend...${NC}"

cd backend

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python -m venv venv
fi

# Ativar ambiente
source venv/bin/activate || . venv/Scripts/activate

# Instalar dependências
if [ ! -f ".env" ]; then
    echo "Copiando .env.example para .env"
    cp .env.example .env
fi

pip install -q -r requirements.txt

echo -e "${GREEN}Backend configurado${NC}"

# Frontend
echo ""
echo -e "${YELLOW}Configurando Frontend...${NC}"

cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Instalando dependências..."
    npm install -q
fi

echo -e "${GREEN}Frontend configurado${NC}"

# Resumo
echo ""
echo "==================================="
echo -e "${GREEN}SmartBling pronto para uso!${NC}"
echo "==================================="
echo ""
echo "Para iniciar:"
echo ""
echo "Terminal 1 - Backend:"
echo "  cd backend"
echo "  source venv/bin/activate (Linux/Mac) ou venv\Scripts\activate (Windows)"
echo "  python main.py run"
echo ""
echo "Terminal 2 - Frontend:"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Acesse: http://localhost:3000"
echo ""
echo "Para configurar API Bling:"
echo "  python main.py configurar"
echo ""
echo "OAuth2 (Bling v3) com ngrok:"
echo "  1) Inicie o backend: cd backend && source venv/bin/activate && python main.py run"
echo "  2) Em outro terminal, inicie o túnel: ngrok http 8000"
echo "  3) Copie a URL pública: https://xxxxx.ngrok-free.app"
echo "  4) No backend/.env, defina: BLING_REDIRECT_URI=https://xxxxx.ngrok-free.app/callback"
echo "  5) Rode: python main.py configurar"
echo "  6) Abra o link de autorização e COLE o code (ou URL completa) no terminal quando solicitado"
echo ""
