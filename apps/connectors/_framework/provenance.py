"""Provenance mixin — every connector ingest row carries source metadata.

Adds (without breaking subclassing):
    source_system     — connector provider code (e.g. "pipedrive", "fapi")
    source_id         — primary key in the source system, indexed
    source_synced_at  — when we last pulled this row
    source_updated_at — last update in source (if available)
    raw_payload       — original JSON response, retention 90 days (purged by cron)
    sync_run          — FK to the SyncRun that wrote this row (nullable)

Tables expecting cross-system queries should additionally hold FKs to
``identity.Person`` and/or ``identity.Organization`` — these aren't included
here because some sync rows (eg. number tables) don't need them.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils import timezone


class ProvenanceMixin(models.Model):
    source_system: models.CharField = models.CharField(max_length=32, db_index=True)
    source_id: models.CharField = models.CharField(max_length=128, db_index=True)
    source_synced_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    source_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    raw_payload: models.JSONField = models.JSONField(default=dict, blank=True)
    sync_run: models.ForeignKey = models.ForeignKey(
        "connectors_framework.SyncRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True
        indexes: ClassVar = [
            models.Index(fields=["source_system", "source_id"]),
        ]
