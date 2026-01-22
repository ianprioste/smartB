#!/bin/bash
# Celery worker startup script for Linux/Mac

cd "$(dirname "$0")/backend" || exit 1
source ../.venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
