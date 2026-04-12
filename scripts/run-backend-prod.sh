#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
LOG_LEVEL="${BACKEND_LOG_LEVEL:-info}"

cd "${REPO_ROOT}/backend"
exec "${REPO_ROOT}/.venv/bin/python" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}"
