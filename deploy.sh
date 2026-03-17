#!/usr/bin/env bash
# Script de deploy para executar direto na VPS
# Uso: ./deploy.sh [branch]
set -Eeuo pipefail

BRANCH="${1:-main}"
COMPOSE_FILE="docker-compose.prod.yml"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
  log "ERRO: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Comando '$1' não encontrado"
}

log "========================================="
log "SmartB - Deploy de Produção"
log "Branch: ${BRANCH}"
log "========================================="

require_cmd git
require_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose plugin não encontrado (comando 'docker compose')"
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  fail "Arquivo '$COMPOSE_FILE' não encontrado"
fi

if [ ! -f .env ]; then
  fail "Arquivo .env não encontrado. Crie com: cp .env.example .env"
fi

log "1/7 - Buscando updates do repositório"
git fetch --all --prune

log "2/7 - Trocando para branch ${BRANCH}"
git checkout "$BRANCH"

log "3/7 - Atualizando código local"
git pull origin "$BRANCH"

log "4/7 - Build das imagens"
docker compose -f "$COMPOSE_FILE" build --pull

log "5/7 - Subindo stack"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

log "6/7 - Aplicando migrações"
alembic_log_file="$(mktemp)"
if ! docker compose -f "$COMPOSE_FILE" exec -T backend alembic upgrade head >"$alembic_log_file" 2>&1; then
  cat "$alembic_log_file"
  if grep -q "DuplicateTable" "$alembic_log_file"; then
    log "Schema legado detectado (tabelas já existentes). Executando alembic stamp head..."
    docker compose -f "$COMPOSE_FILE" exec -T backend alembic stamp head
  else
    rm -f "$alembic_log_file"
    fail "Falha ao aplicar migrações"
  fi
else
  cat "$alembic_log_file"
fi
rm -f "$alembic_log_file"

log "7/7 - Status dos serviços"
docker compose -f "$COMPOSE_FILE" ps

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "${IP}" ]; then
  log "Deploy concluído. App: http://${IP}"
else
  log "Deploy concluído."
fi
