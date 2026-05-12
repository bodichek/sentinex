"""Tenant-scoped models that mirror state from the knowledge graph."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models


class KnowledgeEpisode(models.Model):
    """Audit record of an episode pushed into Graphiti."""

    SOURCE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("message", "Message"),
        ("text", "Text"),
        ("json", "JSON"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default="message")
    source_description = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    graphiti_episode_uuid = models.CharField(max_length=64, blank=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True)
    reference_time: models.DateTimeField[None, None] = models.DateTimeField()
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memory"
        ordering: ClassVar[list[str]] = ["-reference_time"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["source", "-reference_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} @ {self.reference_time:%Y-%m-%d}"


class MemorySnapshot(models.Model):
    """Periodic snapshot of the graph state for audit / debugging."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    captured_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    entity_count = models.IntegerField(default=0)
    edge_count = models.IntegerField(default=0)
    summary = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "memory"
        ordering: ClassVar[list[str]] = ["-captured_at"]

    def __str__(self) -> str:
        return f"snapshot {self.captured_at:%Y-%m-%d %H:%M} ({self.entity_count}n/{self.edge_count}e)"
