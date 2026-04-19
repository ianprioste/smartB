#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  echo "[post-deploy] $*"
}

fail() {
  echo "[post-deploy] ERROR: $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_SERVICE="${BACKEND_SERVICE:-smartbling-backend}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
EXPECT_GIT_COMMIT="${EXPECT_GIT_COMMIT:-}"
REQUIRE_NGINX="${REQUIRE_NGINX:-true}"
WARMUP_PATHS="${WARMUP_PATHS:-/health /api/health /docs}"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

trim() {
  printf '%s' "$1" | sed 's/\r$//;s/^[[:space:]]*//;s/[[:space:]]*$//'
}

extract_git_commit() {
  local payload="$1"
  python3 - "$payload" <<'PY'
import json
import sys

raw = sys.argv[1]
try:
    data = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)

value = data.get("git_commit")
print(str(value or ""))
PY
}

assert_service_active() {
  $SUDO systemctl is-active --quiet "${BACKEND_SERVICE}" || fail "Servico inativo: ${BACKEND_SERVICE}"
}

assert_health() {
  local payload
  payload="$(curl --fail --silent --show-error --retry 8 --retry-delay 2 --retry-connrefused --max-time 5 "${HEALTH_URL}")" || fail "Health-check falhou: ${HEALTH_URL}"

  if [ -n "${EXPECT_GIT_COMMIT}" ]; then
    local got expected_short got_commit
    expected_short="${EXPECT_GIT_COMMIT:0:12}"
    got_commit="$(extract_git_commit "$payload")"
    got="$(trim "$got_commit")"
    if [ -n "$got" ]; then
      if [[ "$got" != *"$expected_short"* && "$got" != *"$EXPECT_GIT_COMMIT"* ]]; then
        fail "git_commit inesperado no health. Esperado ${expected_short} ou ${EXPECT_GIT_COMMIT}, recebido ${got}"
      fi
    else
      log "WARN: health sem git_commit, seguindo validacao sem metadado"
    fi
  fi
}

assert_nginx() {
  [ "${REQUIRE_NGINX}" = "true" ] || return 0
  $SUDO systemctl is-active --quiet nginx || fail "Nginx inativo apos deploy"
  curl --fail --silent --show-error --max-time 5 --insecure "https://127.0.0.1/" > /dev/null 2>&1 || fail "Nginx ativo, mas HTTPS local nao respondeu"
}

warmup_routes() {
  local base
  base="${HEALTH_URL%/health}"

  for path in ${WARMUP_PATHS}; do
    local url
    url="${base}${path}"
    if curl --silent --show-error --max-time 5 "$url" > /dev/null 2>&1; then
      log "Warmup OK: ${url}"
    else
      log "WARN: Warmup falhou (nao bloqueante): ${url}"
    fi
  done
}

main() {
  log "Iniciando validacoes de pos-deploy"
  assert_service_active
  assert_health
  assert_nginx
  warmup_routes
  log "Pos-deploy concluido com sucesso"
}

main "$@"
