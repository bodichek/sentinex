"""Celery application + periodic schedule."""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("sentinex")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Sync Slack every 6 hours, per tenant. The task itself receives a tenant
    # schema; the dispatching wrapper iterates active tenants in production.
    "sync-slack-every-6h": {
        "task": "data_access.sync_slack_dispatch",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}
