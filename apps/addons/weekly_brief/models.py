"""Weekly Brief tenant-scoped models."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models


class WeeklyBriefConfig(models.Model):
    recipients = models.TextField(blank=True, help_text="Comma-separated emails")
    schedule_day = models.IntegerField(default=1, help_text="0=Mon..6=Sun")
    schedule_hour = models.IntegerField(default=7)
    timezone = models.CharField(max_length=64, default="Europe/Prague")
    sections_enabled = models.JSONField(
        default=list,
        blank=True,
        help_text="List of section keys to include",
    )
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "weekly_brief"

    def __str__(self) -> str:
        return f"WeeklyBriefConfig(day={self.schedule_day}, hour={self.schedule_hour})"


class WeeklyBriefReport(models.Model):
    STATUS_PENDING = "pending"
    STATUS_GENERATED = "generated"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (STATUS_PENDING, "Pending"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    content = models.JSONField(default=dict)
    html_body = models.TextField(blank=True)
    plain_body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    generated_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    delivered_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "weekly_brief"
        unique_together = ("period_start", "period_end")
        ordering: ClassVar[list[str]] = ["-period_end"]

    def __str__(self) -> str:
        return f"Brief {self.period_start}..{self.period_end} ({self.status})"
