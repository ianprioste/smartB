#!/bin/bash
# Script de deploy para a VPS Locaweb
# Uso: ./deploy.sh
set -e

echo "========================================="
echo "  SmartB - Deploy de Produção"
echo "========================================="

# Verifica se .env existe
if [ ! -f .env ]; then
  echo "ERRO: arquivo .env não encontrado."
  echo "Copie o .env.example e preencha os valores: cp .env.example .env"
  exit 1
fi

echo ""
echo "1. Atualizando código do repositório..."
git pull origin main

echo ""
echo "2. Construindo imagens Docker..."
docker compose -f docker-compose.prod.yml build --no-cache

echo ""
echo "3. Subindo os serviços..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "4. Aguardando banco de dados ficar pronto..."
sleep 5

echo ""
echo "5. Aplicando migrações do banco de dados..."
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

echo ""
echo "========================================="
echo "  ✅ Deploy concluído!"
IP=$(hostname -I | awk '{print $1}')
echo "  App rodando em: http://$IP"
echo "========================================="
