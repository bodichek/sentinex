"""SyncRun model — per-run execution history for every connector sync."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models


class SyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    PARTIAL = "partial", "Completed with errors"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class SyncMode(models.TextChoices):
    INIT = "init", "Initial backfill"
    INCREMENTAL = "incremental", "Incremental"
    RECONCILE = "reconcile", "Full reconcile"
    WEBHOOK = "webhook", "Webhook-triggered"
    MANUAL = "manual", "Manual trigger"


class SyncRun(models.Model):
    """One execution of a connector sync.

    Indexed on (provider, started_at) so the admin "last 20 runs" view is fast.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration: models.ForeignKey = models.ForeignKey(
        "data_access.Integration",
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    provider: models.CharField = models.CharField(max_length=40, db_index=True)
    mode: models.CharField = models.CharField(
        max_length=16, choices=SyncMode.choices, default=SyncMode.INCREMENTAL
    )
    status: models.CharField = models.CharField(
        max_length=16, choices=SyncStatus.choices, default=SyncStatus.PENDING
    )
    resource: models.CharField = models.CharField(max_length=64, blank=True)  # e.g. "deals", "invoices"
    started_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    finished_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    cursor_before: models.CharField = models.CharField(max_length=255, blank=True)
    cursor_after: models.CharField = models.CharField(max_length=255, blank=True)
    records_fetched: models.IntegerField = models.IntegerField(default=0)
    records_created: models.IntegerField = models.IntegerField(default=0)
    records_updated: models.IntegerField = models.IntegerField(default=0)
    records_skipped: models.IntegerField = models.IntegerField(default=0)
    errors_count: models.IntegerField = models.IntegerField(default=0)
    error_message: models.TextField = models.TextField(blank=True)
    extra: models.JSONField = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "connectors_framework"
        ordering = ("-started_at",)
        indexes: ClassVar = [
            models.Index(fields=["provider", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}.{self.resource}[{self.status}] {self.started_at:%Y-%m-%d %H:%M}"
