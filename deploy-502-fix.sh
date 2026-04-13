#!/bin/bash
# Deploy script for the 502 fix
# Usage: ./deploy-502-fix.sh

set -e

echo "================================"
echo "SmartBling Backend 502 Fix Deploy"
echo "================================"
echo ""

# Configuration
PROJECT_PATH="${1:-.}"
VENV_PATH="${PROJECT_PATH}/.venv"
BACKEND_PATH="${PROJECT_PATH}/backend"

echo "[1] Updating repository..."
cd "$PROJECT_PATH"
git pull origin main
echo "✓ Repository updated"
echo ""

echo "[2] Activating virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    exit 1
fi
source "$VENV_PATH/bin/activate"
echo "✓ Virtual environment activated"
echo ""

echo "[3] Running database migration..."
cd "$BACKEND_PATH"
if ! command -v alembic &> /dev/null; then
    echo "ERROR: alembic not found. Install with: pip install alembic sqlalchemy"
    exit 1
fi

# Run migration
if alembic upgrade head; then
    echo "✓ Database migration completed successfully"
else
    echo "ERROR: Migration failed. Check the error above."
    exit 1
fi
echo ""

echo "[4] Status:"
CURRENT_REVISION=$(alembic current 2>/dev/null || echo "unknown")
echo "Current migration revision: $CURRENT_REVISION"
echo ""

echo "================================"
echo "Deploy completed successfully!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Restart the backend service"
echo "2. Verify the /api/auth/access/login endpoint responds (not 502)"
echo "3. Check logs: journalctl -u smartbling-backend -f"
echo ""
