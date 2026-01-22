"""Celery worker runner for Windows compatibility."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.workers.celery_app import celery_app

if __name__ == "__main__":
    # Run worker with solo pool on Windows
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--pool=solo",  # Force solo pool on Windows
    ])
