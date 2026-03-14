"""
celery_worker.py — Background task queue for FreelancingHub
Run with:  celery -A celery_worker.celery worker --loglevel=info
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# ── Celery app ────────────────────────────────────────────────
_redis = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "freelance_marketplace",
    broker=_redis,
    backend=_redis,
    include=["tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Nairobi",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,       # fair task distribution
    task_acks_late=True,                # only ack after task succeeds
    task_reject_on_worker_lost=True,    # requeue on crash
)