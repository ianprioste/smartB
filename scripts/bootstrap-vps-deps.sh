#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  echo "[bootstrap] $*"
}

if ! command -v apt-get >/dev/null 2>&1; then
  log "apt-get nao disponivel; pulando instalacao automatica de dependencias do sistema"
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive

APT_PACKAGES=(
  ca-certificates
  curl
  git
  python3
  python3-pip
  python3-venv
  nodejs
  npm
)

if command -v python3 >/dev/null 2>&1; then
  PY_MM="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [ -n "$PY_MM" ]; then
    APT_PACKAGES+=("python${PY_MM}-venv")
  fi
fi

log "Atualizando indice de pacotes"
apt-get update

log "Instalando dependencias base: ${APT_PACKAGES[*]}"
apt-get install -y "${APT_PACKAGES[@]}" || apt-get install -y ca-certificates curl git python3 python3-pip python3-venv nodejs npm

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
else
  NODE_MAJOR="0"
fi

if [ "${NODE_MAJOR:-0}" -lt 20 ]; then
  log "Node.js < 20 detectado (${NODE_MAJOR}); instalando Node.js 20.x"
  if [ ! -f /etc/apt/sources.list.d/nodesource.list ]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  else
    apt-get update
  fi
  apt-get install -y nodejs
fi

log "Bootstrap de dependencias concluido"
