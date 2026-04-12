#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  echo "[deploy] $*"
}

fail() {
  echo "[deploy] ERROR: $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_SERVICE="${BACKEND_SERVICE:-${VPS_BACKEND_SERVICE:-smartbling-backend}}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_TARGET_DIR="${FRONTEND_TARGET_DIR:-${VPS_FRONTEND_DIR:-/usr/share/nginx/html}}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-/tmp/smartbling-backend.pid}"
BACKEND_LOG_FILE="${BACKEND_LOG_FILE:-/tmp/smartbling-backend.log}"

cd "${REPO_ROOT}"

bash scripts/bootstrap-vps-deps.sh

if [ -d .venv ] && { [ ! -x ./.venv/bin/python ] || [ ! -x ./.venv/bin/pip ]; }; then
  log ".venv existente esta incompleta; recriando ambiente virtual"
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  log "Criando ambiente virtual Python"
  python3 -m venv .venv || fail "Falha ao criar ambiente virtual Python"
fi

log "Atualizando pip e instalando dependencias do backend"
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r backend/requirements.txt

if [ -f backend/alembic.ini ]; then
  log "Aplicando migrations Alembic"
  (
    cd backend
    ../.venv/bin/python -m alembic -c alembic.ini upgrade head
  )
fi

command -v npm >/dev/null 2>&1 || fail "npm nao encontrado apos bootstrap"
command -v node >/dev/null 2>&1 || fail "node nao encontrado apos bootstrap"
NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/' || echo 0)"
[ "${NODE_MAJOR:-0}" -ge 20 ] || fail "Node.js ${NODE_MAJOR} detectado; Vite exige Node.js 20+"

log "Instalando dependencias do frontend e gerando build"
(
  cd frontend
  npm ci
  npm run build
)

if [ -n "${FRONTEND_TARGET_DIR}" ]; then
  log "Publicando frontend em ${FRONTEND_TARGET_DIR}"
  mkdir -p "${FRONTEND_TARGET_DIR}"
  rm -rf "${FRONTEND_TARGET_DIR}"/*
  cp -a frontend/dist/. "${FRONTEND_TARGET_DIR}/"
fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${BACKEND_SERVICE}\.service"; then
  log "Reiniciando backend via systemd (${BACKEND_SERVICE})"
  systemctl daemon-reload || true
  systemctl restart "${BACKEND_SERVICE}" || {
    systemctl status "${BACKEND_SERVICE}" --no-pager || true
    journalctl -u "${BACKEND_SERVICE}" -n 100 --no-pager || true
    fail "Falha ao reiniciar ${BACKEND_SERVICE}"
  }
else
  log "Service ${BACKEND_SERVICE} nao encontrado; iniciando backend em fallback (nohup)"
  pkill -f "run-backend-prod.sh|backend/run.py|uvicorn app.main:app" >/dev/null 2>&1 || true
  nohup bash scripts/run-backend-prod.sh > "${BACKEND_LOG_FILE}" 2>&1 &
  echo $! > "${BACKEND_PID_FILE}"
fi

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet nginx; then
  log "Recarregando nginx"
  systemctl reload nginx || true
fi

log "Validando health-check ${HEALTH_URL}"
if ! curl --fail --retry 20 --retry-delay 3 "${HEALTH_URL}"; then
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${BACKEND_SERVICE}\.service"; then
    systemctl status "${BACKEND_SERVICE}" --no-pager || true
    journalctl -u "${BACKEND_SERVICE}" -n 100 --no-pager || true
  else
    tail -n 100 "${BACKEND_LOG_FILE}" || true
  fi
  fail "Health-check falhou"
fi

log "Deploy concluido com sucesso"
