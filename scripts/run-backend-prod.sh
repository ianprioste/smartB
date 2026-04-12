#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
LOG_LEVEL="${BACKEND_LOG_LEVEL:-info}"
export PYTHONUNBUFFERED=1
SQLITE_FALLBACK_URL="${SQLITE_FALLBACK_URL:-sqlite:///./smartbling.db}"

normalize_db_url() {
	local raw="$1"
	raw="$(printf '%s' "$raw" | sed 's/\r$//;s/^[[:space:]]*//;s/[[:space:]]*$//')"
	if [[ ${raw:0:1} == '"' && ${raw: -1} == '"' ]]; then
		raw="${raw:1:${#raw}-2}"
	fi
	if [[ ${raw:0:1} == "'" && ${raw: -1} == "'" ]]; then
		raw="${raw:1:${#raw}-2}"
	fi
	printf '%s' "$raw"
}

is_local_pg_down() {
	local db_url="$1"
	if [[ "$db_url" =~ ^postgresql:// ]]; then
		if [[ "$db_url" == *"@localhost:"* || "$db_url" == *"@127.0.0.1:"* || "$db_url" == *"@localhost/"* || "$db_url" == *"@127.0.0.1/"* ]]; then
			if ! timeout 2 bash -c '</dev/tcp/127.0.0.1/5432' 2>/dev/null; then
				return 0
			fi
		fi
	fi
	return 1
}

EFFECTIVE_DB_URL="${DATABASE_URL:-}"
if [ -z "${EFFECTIVE_DB_URL}" ] && [ -f "${REPO_ROOT}/backend/.env" ]; then
	EFFECTIVE_DB_URL="$(grep -E '^DATABASE_URL=' "${REPO_ROOT}/backend/.env" | tail -n 1 | cut -d '=' -f 2- || true)"
fi
EFFECTIVE_DB_URL="$(normalize_db_url "${EFFECTIVE_DB_URL}")"

if is_local_pg_down "${EFFECTIVE_DB_URL}"; then
	echo "[run-backend-prod] PostgreSQL local indisponivel; usando fallback SQLite"
	export DATABASE_URL="${SQLITE_FALLBACK_URL}"
elif [ -n "${EFFECTIVE_DB_URL}" ] && [ -z "${DATABASE_URL:-}" ]; then
	export DATABASE_URL="${EFFECTIVE_DB_URL}"
fi

cd "${REPO_ROOT}/backend"
exec "${REPO_ROOT}/.venv/bin/python" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}"
