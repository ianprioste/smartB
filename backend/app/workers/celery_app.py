"""Celery configuration and task definitions."""
from celery import Celery
from app.settings import settings
import platform

celery_app = Celery(
    "smartbling",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Use solo pool on Windows (prefork doesn't work well on Windows)
pool_type = "solo" if platform.system() == "Windows" else "prefork"

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_pool=pool_type,  # solo on Windows, prefork on Unix
    beat_schedule={
        "orders-incremental-sync": {
            "task": "sync_orders_incremental_task",
            "schedule": max(60, int(settings.ORDERS_INCREMENTAL_SYNC_MINUTES) * 60),
        }
    },
)

# Ensure task decorators are evaluated at import time.
import app.workers.tasks  # noqa: E402,F401
