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
# Normalize optional ".service" suffix from secrets/inputs to avoid double suffixes.
BACKEND_SERVICE="${BACKEND_SERVICE%.service}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_TARGET_DIR="${FRONTEND_TARGET_DIR:-${VPS_FRONTEND_DIR:-/usr/share/nginx/html}}"
MIGRATIONS_MODE="${MIGRATIONS_MODE:-auto}"
PUBLIC_HOST="${PUBLIC_HOST:-app.useruach.com.br}"
GIT_COMMIT="${GIT_COMMIT:-$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"
BUILD_ID="${BUILD_ID:-$(date '+%Y%m%d%H%M%S')-${GIT_COMMIT}}"
BUILD_TIMESTAMP="${BUILD_TIMESTAMP:-$(date -u '+%Y-%m-%dT%H:%M:%SZ')}"
REQUIRE_NGINX="${REQUIRE_NGINX:-true}"
AUTO_FIX_NGINX_PROXY="${AUTO_FIX_NGINX_PROXY:-true}"
DISABLE_LEGACY_DOCKER="${DISABLE_LEGACY_DOCKER:-true}"
SYSTEMD_USER="${SYSTEMD_USER:-root}"
BACKEND_ENV_B64="${BACKEND_ENV_B64:-}"
DEPLOY_SECRET_KEY="${DEPLOY_SECRET_KEY:-}"
DEPLOY_DATABASE_URL="${DEPLOY_DATABASE_URL:-}"
DEPLOY_CORS_ORIGINS="${DEPLOY_CORS_ORIGINS:-}"
DEPLOY_BLING_CLIENT_ID="${DEPLOY_BLING_CLIENT_ID:-}"
DEPLOY_BLING_CLIENT_SECRET="${DEPLOY_BLING_CLIENT_SECRET:-}"
DEPLOY_BLING_REDIRECT_URI="${DEPLOY_BLING_REDIRECT_URI:-}"
DEPLOY_SMTP_HOST="${DEPLOY_SMTP_HOST:-}"
DEPLOY_SMTP_PORT="${DEPLOY_SMTP_PORT:-}"
DEPLOY_SMTP_USERNAME="${DEPLOY_SMTP_USERNAME:-}"
DEPLOY_SMTP_PASSWORD="${DEPLOY_SMTP_PASSWORD:-}"
DEPLOY_SMTP_FROM_EMAIL="${DEPLOY_SMTP_FROM_EMAIL:-}"
DEPLOY_SMTP_FROM_NAME="${DEPLOY_SMTP_FROM_NAME:-}"

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
    upsert_env_key CORS_ORIGINS "https://${PUBLIC_HOST}"
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
  [ -n "$DEPLOY_SMTP_HOST" ] && upsert_env_key SMTP_HOST "$DEPLOY_SMTP_HOST"
  [ -n "$DEPLOY_SMTP_PORT" ] && upsert_env_key SMTP_PORT "$DEPLOY_SMTP_PORT"
  [ -n "$DEPLOY_SMTP_USERNAME" ] && upsert_env_key SMTP_USERNAME "$DEPLOY_SMTP_USERNAME"
  [ -n "$DEPLOY_SMTP_PASSWORD" ] && upsert_env_key SMTP_PASSWORD "$DEPLOY_SMTP_PASSWORD"
  [ -n "$DEPLOY_SMTP_FROM_EMAIL" ] && upsert_env_key SMTP_FROM_EMAIL "$DEPLOY_SMTP_FROM_EMAIL"
  [ -n "$DEPLOY_SMTP_FROM_NAME" ] && upsert_env_key SMTP_FROM_NAME "$DEPLOY_SMTP_FROM_NAME"
  return 0
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

validate_local_public_rollout() {
  local expected_short
  expected_short="${GIT_COMMIT:0:12}"

  curl --fail --silent --show-error --location --insecure --max-time 8 "http://127.0.0.1/build-info.json" > /tmp/local-build-info.json || fail "Nginx local nao serviu /build-info.json"
  curl --fail --silent --show-error --location --insecure --max-time 8 "http://127.0.0.1/api/health" > /tmp/local-health.json || fail "Nginx local nao serviu /api/health"

  python3 - <<'PY'
import json
import os

expected = os.environ.get("GIT_COMMIT", "")
expected_short = expected[:12]

with open('/tmp/local-build-info.json', 'r', encoding='utf-8') as f:
    build_raw = f.read()
with open('/tmp/local-health.json', 'r', encoding='utf-8') as f:
    health_raw = f.read()

try:
    build = json.loads(build_raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"Local /build-info.json nao e JSON valido: {exc}; inicio={build_raw[:180]!r}")

try:
    health = json.loads(health_raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"Local /api/health nao e JSON valido: {exc}; inicio={health_raw[:180]!r}")

build_commit = str(build.get('git_commit', ''))
health_commit = str(health.get('git_commit', ''))

if expected_short not in build_commit and expected not in build_commit:
    raise SystemExit(f"Local /build-info.json desatualizado. Esperado {expected_short} ou {expected}, recebido {build_commit}")
if expected_short not in health_commit and expected not in health_commit:
    raise SystemExit(f"Local /api/health desatualizado. Esperado {expected_short} ou {expected}, recebido {health_commit}")

print("Local public rollout verified")
PY
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
    if grep -qE 'proxy_pass[[:space:]]+http://backend:8000/?' "$f" 2>/dev/null; then
      sed -i -E 's#proxy_pass[[:space:]]+http://backend:8000/?#proxy_pass http://127.0.0.1:8000/#g' "$f"
      changed=1
      log "Ajustado proxy nginx em $f"
    fi
  done <<< "$files"

  if [ "$changed" -eq 1 ]; then
    nginx -t || fail "nginx invalido apos ajuste automatico de proxy"
    systemctl reload nginx || fail "Falha ao recarregar nginx apos ajuste automatico"
  fi
}

stop_legacy_docker_ingress() {
  [ "${DISABLE_LEGACY_DOCKER}" = "true" ] || return 0

  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local legacy_rows cid proxy_listeners
  legacy_rows="$(
    docker ps --format '{{.ID}}\t{{.Ports}}' \
      | awk -F '\t' '$2 ~ /(^|, )[[:space:]]*[^,]*:(80|443|8000)->/ { print }' \
      || true
  )"

  if [ -n "$legacy_rows" ]; then
    warn "Containers Docker com publish em 80/443/8000 detectados; desativando para evitar conflito com nginx"
    while IFS= read -r row; do
      [ -n "$row" ] || continue
      cid="$(printf '%s' "$row" | awk -F '\t' '{print $1}')"
      [ -n "$cid" ] || continue
      docker update --restart=no "$cid" >/dev/null 2>&1 || true
      docker stop "$cid" >/dev/null 2>&1 || true
      docker rm "$cid" >/dev/null 2>&1 || true
    done <<< "$legacy_rows"
  fi

  proxy_listeners=""
  if command -v ss >/dev/null 2>&1; then
    proxy_listeners="$(ss -ltnp 2>/dev/null | awk '/:(80|8000)[[:space:]]/ && /docker-proxy/ { print }' || true)"
  elif command -v lsof >/dev/null 2>&1; then
    proxy_listeners="$(lsof -nP -iTCP:80 -iTCP:8000 -sTCP:LISTEN 2>/dev/null | awk '/docker-proxy/ { print }' || true)"
  else
    warn "Nem ss nem lsof disponiveis para verificar listeners docker-proxy em 80/8000"
  fi

  if [ -n "$proxy_listeners" ]; then
    printf '%s\n' "$proxy_listeners" >&2
    fail "docker-proxy ainda escutando em 80/8000 apos limpeza de containers legados. Interrompendo deploy para evitar conflito de ingress."
  fi
}

enforce_nginx_public_server() {
  [ "$REQUIRE_NGINX" = "true" ] || return 0

  local conf_path cert_path is_ip
  conf_path="/etc/nginx/conf.d/smartbling-public.conf"
  cert_path="/etc/letsencrypt/live/${PUBLIC_HOST}/fullchain.pem"

  # Detect whether PUBLIC_HOST is a bare IP address
  is_ip=false
  if printf '%s' "$PUBLIC_HOST" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    is_ip=true
  fi

  if [ "$is_ip" = "false" ] && [ -f "$cert_path" ]; then
    # ── HTTPS mode ────────────────────────────────────────────────
    log "Certificado SSL detectado; configurando nginx com HTTPS"
    cat > "$conf_path" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${PUBLIC_HOST};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${PUBLIC_HOST};

    ssl_certificate     /etc/letsencrypt/live/${PUBLIC_HOST}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${PUBLIC_HOST}/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/${PUBLIC_HOST}/chain.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml+rss text/javascript;
    gzip_min_length 1000;

    root ${FRONTEND_TARGET_DIR};
    index index.html;

    location = /index.html {
        add_header Cache-Control "no-store, must-revalidate";
    }

    location = /build-info.json {
        add_header Cache-Control "no-store, must-revalidate";
        try_files /build-info.json =404;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix /api;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_connect_timeout 10s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
  else
    # ── HTTP-only mode (cert nao existe ainda, ou PUBLIC_HOST e IP) ──
    local listen_v4 listen_v6
    listen_v4="listen 80;"
    listen_v6="listen [::]:80;"

    if ! nginx -T 2>/dev/null | grep -qE 'listen[[:space:]]+80[[:space:]]+default_server'; then
      listen_v4="listen 80 default_server;"
      listen_v6="listen [::]:80 default_server;"
    fi

    cat > "$conf_path" <<EOF
server {
    ${listen_v4}
    ${listen_v6}
    server_name ${PUBLIC_HOST};

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml+rss text/javascript;
    gzip_min_length 1000;

    root ${FRONTEND_TARGET_DIR};
    index index.html;

    location = /index.html {
        add_header Cache-Control "no-store, must-revalidate";
    }

    location = /build-info.json {
        add_header Cache-Control "no-store, must-revalidate";
        try_files /build-info.json =404;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix /api;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_connect_timeout 10s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
  fi

  if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
  fi

  nginx -t || fail "nginx invalido apos instalar smartbling-public.conf"
  systemctl reload nginx || fail "Falha ao recarregar nginx apos instalar smartbling-public.conf"
  log "Configuracao nginx publica reforcada em $conf_path"
}

provision_ssl_cert() {
  local cert_path email

  # Skip if PUBLIC_HOST is a bare IP — Let's Encrypt nao emite certs para IPs
  if printf '%s' "$PUBLIC_HOST" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    log "PUBLIC_HOST e um endereco IP; ignorando provisionamento de certificado SSL"
    return 0
  fi

  cert_path="/etc/letsencrypt/live/${PUBLIC_HOST}/fullchain.pem"

  if [ -f "$cert_path" ]; then
    log "Certificado SSL ja existe para ${PUBLIC_HOST}; nenhuma acao necessaria"
    return 0
  fi

  if ! command -v certbot >/dev/null 2>&1; then
    warn "certbot nao encontrado; ignorando provisionamento SSL automatico"
    return 0
  fi

  email="$(env_value SMTP_FROM_EMAIL)"
  email="${email:-ian.prioste@useruach.com.br}"

  log "Obtendo certificado Let's Encrypt para ${PUBLIC_HOST} (email: ${email})"
  if certbot certonly --nginx \
      -d "$PUBLIC_HOST" \
      --non-interactive \
      --agree-tos \
      --email "$email" \
      --no-eff-email; then
    log "Certificado SSL obtido com sucesso; aplicando configuracao nginx com HTTPS"
    enforce_nginx_public_server
  else
    warn "Falha ao obter certificado SSL para ${PUBLIC_HOST}; aplicacao permanecera em HTTP"
  fi
}
publish_frontend_atomic() {
  local target="$1"
  local tmp_target prev_target
  [ -n "$target" ] || fail "Diretorio de publicacao frontend vazio"
  [ "$target" != "/" ] || fail "Diretorio de publicacao frontend invalido: /"
  tmp_target="${target}.next"
  prev_target="${target}.prev"

  mkdir -p "$(dirname "$target")"
  rm -rf "$tmp_target"
  mkdir -p "$tmp_target"
  cp -a frontend/dist/. "$tmp_target/"
  [ -f "$tmp_target/index.html" ] || fail "index.html ausente no build frontend"

  rm -rf "$prev_target"
  if [ -e "$target" ] || [ -L "$target" ]; then
    mv "$target" "$prev_target"
  fi
  mv "$tmp_target" "$target"
  log "Frontend publicado atomicamente em $target"
}

sync_frontend_to_nginx_roots() {
  local roots root
  roots="$(nginx -T 2>/dev/null | sed -n 's/^[[:space:]]*root[[:space:]]\+\([^;][^;]*\);/\1/p' | sed 's/[[:space:]]*$//' | sort -u || true)"

  # Add common roots defensively to avoid stale serving path drift.
  roots="$(printf '%s\n%s\n%s\n' "$roots" '/usr/share/nginx/html' '/var/www/html' | sed '/^$/d' | sort -u)"

  while IFS= read -r root; do
    [ -n "$root" ] || continue
    case "$root" in
      /*)
        if [ "$root" != "$FRONTEND_TARGET_DIR" ] && [ "$root" != "/" ]; then
          log "Sincronizando frontend tambem para root nginx: $root"
          publish_frontend_atomic "$root"
        fi
        ;;
    esac
  done <<< "$roots"
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

backend_unit_exists() {
  local unit_name unit_path
  unit_name="${BACKEND_SERVICE}.service"
  unit_path="/etc/systemd/system/${unit_name}"

  if [ -f "$unit_path" ]; then
    return 0
  fi

  systemctl cat "${BACKEND_SERVICE}" >/dev/null 2>&1
}

free_backend_port_conflicts() {
  local service_pid listener_pid

  service_pid="$(systemctl show -p MainPID --value "${BACKEND_SERVICE}" 2>/dev/null || echo 0)"
  service_pid="${service_pid:-0}"

  listener_pid=""
  if command -v ss >/dev/null 2>&1; then
    listener_pid="$(ss -ltnp 2>/dev/null | sed -n 's/.*:8000[[:space:]].*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
  elif command -v lsof >/dev/null 2>&1; then
    listener_pid="$(lsof -nP -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null | head -n 1)"
  fi

  if [ -n "${listener_pid}" ] && [ "${listener_pid}" != "${service_pid}" ]; then
    warn "Processo nao gerenciado ocupando porta 8000 (pid=${listener_pid}); encerrando para liberar backend"
    kill "${listener_pid}" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "${listener_pid}" >/dev/null 2>&1; then
      kill -9 "${listener_pid}" >/dev/null 2>&1 || true
    fi
  fi
}

require_cmd git
require_cmd python3
require_cmd npm
require_cmd node
require_cmd systemctl
require_cmd curl
require_cmd nginx

if ! backend_unit_exists; then
  log "Unit ${BACKEND_SERVICE}.service nao encontrada; instalando unit de producao"
fi

install_backend_systemd_unit

if ! backend_unit_exists; then
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

if [ -f backend/smartbling.db ]; then
  log "Aplicando reparo SQL legado para colunas de tags no SQLite"
  ./.venv/bin/python - <<'PY'
import sqlite3

db_path = "backend/smartbling.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

checks = [
    ("order_tag_links", "created_at", "ALTER TABLE order_tag_links ADD COLUMN created_at DATETIME"),
    ("order_tag_links", "updated_at", "ALTER TABLE order_tag_links ADD COLUMN updated_at DATETIME"),
    ("order_tags", "name_key", "ALTER TABLE order_tags ADD COLUMN name_key VARCHAR(80)"),
    ("order_tags", "created_at", "ALTER TABLE order_tags ADD COLUMN created_at DATETIME"),
    ("order_tags", "updated_at", "ALTER TABLE order_tags ADD COLUMN updated_at DATETIME"),
    ("order_tag_assignments", "created_at", "ALTER TABLE order_tag_assignments ADD COLUMN created_at DATETIME"),
    ("order_tag_assignments", "updated_at", "ALTER TABLE order_tag_assignments ADD COLUMN updated_at DATETIME"),
]

for table, column, ddl in checks:
    cols = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        cur.execute(ddl)

conn.commit()
conn.close()
PY
fi

if [ -f backend/alembic.ini ]; then
  if [ "${MIGRATIONS_MODE}" = "off" ]; then
    log "Migrations desativadas por MIGRATIONS_MODE=off"
  else
    log "Aplicando migrations Alembic"
    if ! (
      cd backend
      ../.venv/bin/python -m alembic -c alembic.ini upgrade head
    ); then
      if [ "${MIGRATIONS_MODE}" = "required" ]; then
        fail "Falha ao aplicar migrations com MIGRATIONS_MODE=required"
      fi
      warn "Falha ao aplicar migrations; continuando deploy com MIGRATIONS_MODE=${MIGRATIONS_MODE}"
    fi
  fi
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
  publish_frontend_atomic "$FRONTEND_TARGET_DIR"
  sync_frontend_to_nginx_roots
fi

stop_legacy_docker_ingress
enforce_nginx_public_server
provision_ssl_cert

log "Reiniciando backend via systemd (${BACKEND_SERVICE})"
free_backend_port_conflicts
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

log "Validando rollout local via nginx (build-info + api/health)"
validate_local_public_rollout

health_payload="$(curl --fail --silent --show-error "${HEALTH_URL}")"
if ! printf '%s' "$health_payload" | grep -q "\"git_commit\""; then
  warn "Health sem metadado git_commit; validacao estrita sera feita no step externo do workflow"
fi

log "Deploy remoto concluido; verificacao de commit publico segue no workflow"
log "Deploy concluido com sucesso"
