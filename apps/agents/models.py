"""Tenant-scoped models: agent conversations, extracted facts, memory embeddings."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models
from pgvector.django import VectorField


class Conversation(models.Model):
    external_id = models.CharField(max_length=64, db_index=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    mask_map = models.JSONField(default=dict, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "agents"
        ordering: ClassVar[list[str]] = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversation #{self.pk}"


class ConversationMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (ROLE_USER, "User"), (ROLE_ASSISTANT, "Assistant"), (ROLE_SYSTEM, "System"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    masked = models.BooleanField(default=False)
    tokens = models.IntegerField(default=0)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "agents"
        ordering: ClassVar[list[str]] = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"


class ExtractedFact(models.Model):
    """Medium-term memory: structured fact extracted from conversations."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name="facts"
    )
    key = models.CharField(max_length=100, db_index=True)
    value = models.TextField()
    confidence = models.FloatField(default=1.0)
    source = models.CharField(max_length=100, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    expires_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "agents"
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["key", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.key} = {self.value[:60]}"


class MemoryEmbedding(models.Model):
    """Long-term memory: text + 1536-dim embedding for cosine RAG.

    Table is created via raw SQL in migration ``0002_memoryembedding`` so the
    pgvector extension can be checked first. ``managed = False`` keeps Django
    from auto-issuing CREATE TABLE via stock migrations.
    """

    SOURCE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("insight", "Insight"),
        ("brief", "Brief"),
        ("chat", "Chat"),
        ("document", "Document"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_user = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memory_embeddings",
        db_constraint=False,
    )
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, db_index=True)
    content = models.TextField()
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "agents"
        managed = False
        db_table = "agents_memoryembedding"

    def __str__(self) -> str:
        return f"{self.source}:{str(self.id)[:8]} {self.content[:50]}"
