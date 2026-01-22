"""Celery worker startup script."""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.workers.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()
