#!/usr/bin/env bash
set -Eeuo pipefail

# Health check com auto-restart: verifica a cada 30s se o backend responde
# Se não responder em 2 tentativas, mata o service e deixa systemd reiniciar

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
SERVICE_NAME="${SERVICE_NAME:-smartbling-backend}"
CHECK_INTERVAL=30
FAIL_THRESHOLD=2
FAIL_COUNT=0

log() { echo "[health-check] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

log "Iniciando health check para $SERVICE_NAME (URL: $HEALTH_URL)"

while true; do
    sleep "$CHECK_INTERVAL"
    
    if curl --silent --show-error --max-time 8 "$HEALTH_URL" > /dev/null 2>&1; then
        [ "$FAIL_COUNT" -gt 0 ] && log "✓ Backend respondendo novamente"
        FAIL_COUNT=0
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        log "✗ Backend NÃO RESPONDEU (tentativa $FAIL_COUNT/$FAIL_THRESHOLD)"
        
        if [ "$FAIL_COUNT" -ge "$FAIL_THRESHOLD" ]; then
            log "⚠ MATANDO SERVICE para forçar restart automático"
            sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || systemctl stop "$SERVICE_NAME" || killall python 2>/dev/null || true
            log "ℹ Aguardando systemd reiniciar (aguardando 10s)..."
            sleep 10
            FAIL_COUNT=0
        fi
    fi
done
