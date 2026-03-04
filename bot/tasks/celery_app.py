"""
RefLens — Celery App
"""
from celery import Celery
from celery.schedules import crontab

from bot.config import settings

app = Celery("reflens_tasks")

app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_default_queue="default",
    imports=("bot.tasks.reminders",),
    beat_schedule={
        "send-subscription-reminders-daily": {
            "task": "bot.tasks.reminders.send_subscription_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
        "cleanup-old-logs-weekly": {
            "task": "bot.tasks.reminders.cleanup_old_logs",
            "schedule": crontab(day_of_week="monday", hour=3, minute=0),
        },
    },
)
