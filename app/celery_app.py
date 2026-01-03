from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "vivbliss",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    worker_max_tasks_per_child=100,
    beat_schedule={
        "daily-crawl": {
            "task": "app.tasks.crawl_site",
            "schedule": crontab(minute=0, hour=0),
        },
        "dispatch-outbox": {
            "task": "app.tasks.dispatch_outbox",
            "schedule": crontab(minute="*"),
        },
    },
)
