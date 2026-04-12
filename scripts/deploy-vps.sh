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
MIGRATIONS_MODE="${MIGRATIONS_MODE:-required}"
PUBLIC_HOST="${PUBLIC_HOST:-191.252.204.67}"
GIT_COMMIT="${GIT_COMMIT:-$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"
BUILD_ID="${BUILD_ID:-$(date '+%Y%m%d%H%M%S')-${GIT_COMMIT}}"
BUILD_TIMESTAMP="${BUILD_TIMESTAMP:-$(date -u '+%Y-%m-%dT%H:%M:%SZ')}"
REQUIRE_NGINX="${REQUIRE_NGINX:-true}"
AUTO_FIX_NGINX_PROXY="${AUTO_FIX_NGINX_PROXY:-true}"
SYSTEMD_USER="${SYSTEMD_USER:-root}"
BACKEND_ENV_B64="${BACKEND_ENV_B64:-}"
DEPLOY_SECRET_KEY="${DEPLOY_SECRET_KEY:-}"
DEPLOY_DATABASE_URL="${DEPLOY_DATABASE_URL:-}"
DEPLOY_CORS_ORIGINS="${DEPLOY_CORS_ORIGINS:-}"
DEPLOY_BLING_CLIENT_ID="${DEPLOY_BLING_CLIENT_ID:-}"
DEPLOY_BLING_CLIENT_SECRET="${DEPLOY_BLING_CLIENT_SECRET:-}"
DEPLOY_BLING_REDIRECT_URI="${DEPLOY_BLING_REDIRECT_URI:-}"

cd "${REPO_ROOT}"

trim() {
  printf '%s' "$1" | sed 's/\r$//;s/^[[:space:]]*//;s/[[:space:]]*$//'
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Comando obrigatorio nao encontrado: $1"
}

warn() {
  echo "[deploy] WARN: $*"
}

env_value() {
  local key="$1"
  local val
  val="$(grep -E "^${key}=" backend/.env | tail -n 1 | cut -d '=' -f 2- || true)"
  val="$(trim "$val")"
  if [[ ${val:0:1} == '"' && ${val: -1} == '"' ]]; then
    val="${val:1:${#val}-2}"
  fi
  if [[ ${val:0:1} == "'" && ${val: -1} == "'" ]]; then
    val="${val:1:${#val}-2}"
  fi
  printf '%s' "$val"
}

assert_not_empty() {
  local key="$1"
  local val="$2"
  [ -n "$val" ] || fail "Variavel obrigatoria ausente em backend/.env: $key"
}

bootstrap_backend_env() {
  if [ -f backend/.env ]; then
    return 0
  fi

  if [ -n "${BACKEND_ENV_B64}" ]; then
    log "Criando backend/.env a partir de BACKEND_ENV_B64"
    printf '%s' "${BACKEND_ENV_B64}" | base64 -d > backend/.env || fail "Falha ao decodificar BACKEND_ENV_B64"
    return 0
  fi

  if [ -f backend/.env.example ]; then
    log "backend/.env ausente; copiando backend/.env.example"
    cp backend/.env.example backend/.env
    return 0
  fi

  fail "backend/.env ausente e sem backend/.env.example para bootstrap"
}

ensure_env_defaults() {
  local cors_origins
  cors_origins="$(env_value CORS_ORIGINS)"
  if [ -z "$cors_origins" ]; then
    log "CORS_ORIGINS ausente; definindo padrao seguro para ${PUBLIC_HOST}"
    upsert_env_key CORS_ORIGINS "http://${PUBLIC_HOST}"
  fi
}

is_local_postgres_unreachable() {
  local db_url="$1"
  if [[ "$db_url" =~ ^(postgres|postgresql)(\+[a-zA-Z0-9_]+)?:// ]]; then
    if [[ "$db_url" == *"@localhost:"* || "$db_url" == *"@127.0.0.1:"* || "$db_url" == *"@localhost/"* || "$db_url" == *"@127.0.0.1/"* ]]; then
      if ! timeout 2 bash -c '</dev/tcp/127.0.0.1/5432' 2>/dev/null; then
        return 0
      fi
    fi
  fi
  return 1
}

ensure_runtime_safe_defaults() {
  local secret_key database_url bling_id bling_secret generated_key
  secret_key="$(env_value SECRET_KEY)"
  database_url="$(env_value DATABASE_URL)"
  bling_id="$(env_value BLING_CLIENT_ID)"
  bling_secret="$(env_value BLING_CLIENT_SECRET)"

  if [ -z "$secret_key" ] || [ "$secret_key" = "dev-secret-key-change-in-production" ] || [ "$secret_key" = "your-secret-key-change-in-production" ]; then
    generated_key="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
    upsert_env_key SECRET_KEY "$generated_key"
    warn "SECRET_KEY gerada automaticamente para viabilizar o deploy"
  fi

  if [ -z "$database_url" ]; then
    upsert_env_key DATABASE_URL "sqlite:///./smartbling.db"
    warn "DATABASE_URL ausente; definido fallback sqlite:///./smartbling.db"
  elif is_local_postgres_unreachable "$database_url"; then
    upsert_env_key DATABASE_URL "sqlite:///./smartbling.db"
    warn "PostgreSQL local indisponivel; ajustado DATABASE_URL para sqlite:///./smartbling.db"
  fi

  if [ -z "$bling_id" ] || [ "$bling_id" = "your_client_id_here" ]; then
    warn "BLING_CLIENT_ID ausente/placeholder; recursos Bling podem ficar indisponiveis"
  fi
  if [ -z "$bling_secret" ] || [ "$bling_secret" = "your_client_secret_here" ]; then
    warn "BLING_CLIENT_SECRET ausente/placeholder; recursos Bling podem ficar indisponiveis"
  fi
}

hydrate_env_from_inputs() {
  [ -n "$DEPLOY_SECRET_KEY" ] && upsert_env_key SECRET_KEY "$DEPLOY_SECRET_KEY"
  [ -n "$DEPLOY_DATABASE_URL" ] && upsert_env_key DATABASE_URL "$DEPLOY_DATABASE_URL"
  [ -n "$DEPLOY_CORS_ORIGINS" ] && upsert_env_key CORS_ORIGINS "$DEPLOY_CORS_ORIGINS"
  [ -n "$DEPLOY_BLING_CLIENT_ID" ] && upsert_env_key BLING_CLIENT_ID "$DEPLOY_BLING_CLIENT_ID"
  [ -n "$DEPLOY_BLING_CLIENT_SECRET" ] && upsert_env_key BLING_CLIENT_SECRET "$DEPLOY_BLING_CLIENT_SECRET"
  [ -n "$DEPLOY_BLING_REDIRECT_URI" ] && upsert_env_key BLING_REDIRECT_URI "$DEPLOY_BLING_REDIRECT_URI"
}

upsert_env_key() {
  local key="$1"
  local val="$2"
  local escaped
  escaped="$(printf '%s' "$val" | sed 's/[&/]/\\&/g')"
  if grep -qE "^${key}=" backend/.env; then
    sed -i "s#^${key}=.*#${key}=${escaped}#" backend/.env
  else
    printf '\n%s=%s\n' "$key" "$val" >> backend/.env
  fi
}

validate_backend_env() {
  [ -f backend/.env ] || fail "Arquivo backend/.env nao encontrado na VPS"

  local secret_key database_url cors_origins bling_id bling_secret
  secret_key="$(env_value SECRET_KEY)"
  database_url="$(env_value DATABASE_URL)"
  cors_origins="$(env_value CORS_ORIGINS)"
  bling_id="$(env_value BLING_CLIENT_ID)"
  bling_secret="$(env_value BLING_CLIENT_SECRET)"

  assert_not_empty SECRET_KEY "$secret_key"
  assert_not_empty DATABASE_URL "$database_url"
  assert_not_empty CORS_ORIGINS "$cors_origins"

  [ "$secret_key" != "dev-secret-key-change-in-production" ] || fail "SECRET_KEY insegura (default de desenvolvimento)"
  [ "$secret_key" != "your-secret-key-change-in-production" ] || fail "SECRET_KEY placeholder detectada"
  if echo "$cors_origins" | grep -qiE 'localhost:5173|localhost:3000'; then
    fail "CORS_ORIGINS contem endpoints de desenvolvimento: $cors_origins"
  fi

  if [ -z "$bling_id" ] || [ "$bling_id" = "your_client_id_here" ]; then
    warn "BLING_CLIENT_ID ausente/placeholder; integracao Bling nao estara pronta"
  fi
  if [ -z "$bling_secret" ] || [ "$bling_secret" = "your_client_secret_here" ]; then
    warn "BLING_CLIENT_SECRET ausente/placeholder; integracao Bling nao estara pronta"
  fi
}

fix_nginx_backend_proxy() {
  [ "$AUTO_FIX_NGINX_PROXY" = "true" ] || return 0
  local files
  files="$(find /etc/nginx/sites-enabled /etc/nginx/sites-available /etc/nginx/conf.d -maxdepth 1 -type f 2>/dev/null || true)"
  [ -n "$files" ] || return 0

  local changed=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if grep -q 'proxy_pass http://backend:8000/' "$f" 2>/dev/null; then
      sed -i 's#proxy_pass http://backend:8000/#proxy_pass http://127.0.0.1:8000/#g' "$f"
      changed=1
      log "Ajustado proxy nginx em $f"
    fi
  done <<< "$files"

  if [ "$changed" -eq 1 ]; then
    nginx -t || fail "nginx invalido apos ajuste automatico de proxy"
    systemctl reload nginx || fail "Falha ao recarregar nginx apos ajuste automatico"
  fi
}

publish_frontend_atomic() {
  local tmp_target prev_target
  tmp_target="${FRONTEND_TARGET_DIR}.next"
  prev_target="${FRONTEND_TARGET_DIR}.prev"

  mkdir -p "$(dirname "$FRONTEND_TARGET_DIR")"
  rm -rf "$tmp_target"
  mkdir -p "$tmp_target"
  cp -a frontend/dist/. "$tmp_target/"
  [ -f "$tmp_target/index.html" ] || fail "index.html ausente no build frontend"

  rm -rf "$prev_target"
  if [ -e "$FRONTEND_TARGET_DIR" ] || [ -L "$FRONTEND_TARGET_DIR" ]; then
    mv "$FRONTEND_TARGET_DIR" "$prev_target"
  fi
  mv "$tmp_target" "$FRONTEND_TARGET_DIR"
  log "Frontend publicado atomicamente em $FRONTEND_TARGET_DIR"
}

install_backend_systemd_unit() {
  local unit_path template_path
  unit_path="/etc/systemd/system/${BACKEND_SERVICE}.service"
  template_path="${REPO_ROOT}/deploy/systemd/smartbling-backend.service"

  if [ -f "$template_path" ]; then
    cp "$template_path" "$unit_path"
    sed -i "s#^User=.*#User=${SYSTEMD_USER}#" "$unit_path"
    sed -i "s#^WorkingDirectory=.*#WorkingDirectory=${REPO_ROOT}#" "$unit_path"
    sed -i "s#^ExecStart=.*#ExecStart=/usr/bin/env bash ${REPO_ROOT}/scripts/run-backend-prod.sh#" "$unit_path"
  else
    cat > "$unit_path" <<EOF
[Unit]
Description=smartBling FastAPI backend
After=network.target

[Service]
Type=simple
User=${SYSTEMD_USER}
WorkingDirectory=${REPO_ROOT}
Environment=BACKEND_HOST=0.0.0.0
Environment=BACKEND_PORT=8000
Environment=BACKEND_LOG_LEVEL=info
ExecStart=/usr/bin/env bash ${REPO_ROOT}/scripts/run-backend-prod.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  fi

  systemctl daemon-reload
  systemctl enable "${BACKEND_SERVICE}" >/dev/null 2>&1 || true
}

require_cmd git
require_cmd python3
require_cmd npm
require_cmd node
require_cmd systemctl
require_cmd curl
require_cmd nginx

if ! systemctl list-unit-files | grep -q "^${BACKEND_SERVICE}\.service"; then
  log "Unit ${BACKEND_SERVICE}.service nao encontrada; instalando unit de producao"
  install_backend_systemd_unit
fi

if ! systemctl list-unit-files | grep -q "^${BACKEND_SERVICE}\.service"; then
  fail "Falha ao instalar unit systemd obrigatoria: ${BACKEND_SERVICE}.service"
fi

bootstrap_backend_env
hydrate_env_from_inputs
ensure_env_defaults
ensure_runtime_safe_defaults
validate_backend_env

upsert_env_key GIT_COMMIT "$GIT_COMMIT"
upsert_env_key BUILD_ID "$BUILD_ID"
upsert_env_key BUILD_TIMESTAMP "$BUILD_TIMESTAMP"

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
  [ "${MIGRATIONS_MODE}" = "required" ] || fail "MIGRATIONS_MODE deve ser required em producao"
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

cat > frontend/dist/build-info.json <<EOF
{
  "git_commit": "${GIT_COMMIT}",
  "build_id": "${BUILD_ID}",
  "build_timestamp": "${BUILD_TIMESTAMP}"
}
EOF

if [ -n "${FRONTEND_TARGET_DIR}" ]; then
  publish_frontend_atomic
fi

log "Reiniciando backend via systemd (${BACKEND_SERVICE})"
systemctl daemon-reload || true
systemctl restart "${BACKEND_SERVICE}" || {
  systemctl status "${BACKEND_SERVICE}" --no-pager || true
  journalctl -u "${BACKEND_SERVICE}" -n 150 --no-pager || true
  fail "Falha ao reiniciar ${BACKEND_SERVICE}"
}
systemctl is-active --quiet "${BACKEND_SERVICE}" || fail "${BACKEND_SERVICE} nao ficou ativo apos restart"

fix_nginx_backend_proxy

if [ "${REQUIRE_NGINX}" = "true" ]; then
  systemctl is-active --quiet nginx || fail "Nginx precisa estar ativo em producao"
  nginx -t || fail "Configuracao nginx invalida"
  log "Recarregando nginx"
  systemctl reload nginx || fail "Falha ao recarregar nginx"
fi

log "Validando health-check ${HEALTH_URL}"
if ! curl --fail --silent --show-error --retry 20 --retry-delay 3 --retry-connrefused --max-time 5 "${HEALTH_URL}"; then
  systemctl status "${BACKEND_SERVICE}" --no-pager || true
  journalctl -u "${BACKEND_SERVICE}" -n 150 --no-pager || true
  fail "Health-check falhou"
fi

health_payload="$(curl --fail --silent --show-error "${HEALTH_URL}")"
printf '%s' "$health_payload" | grep -q "\"git_commit\"" || fail "Health sem metadado git_commit"
printf '%s' "$health_payload" | grep -q "${GIT_COMMIT}" || fail "Health nao corresponde ao commit esperado ${GIT_COMMIT}"

log "Validando artefato publico de build"
curl --fail --silent --show-error "http://${PUBLIC_HOST}/build-info.json?b=${BUILD_ID}" | grep -q "${GIT_COMMIT}" || fail "build-info publico nao corresponde ao commit esperado"

log "Deploy concluido com sucesso"
