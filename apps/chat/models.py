"""Chat models — tenant-schema (one Conversation per user thread)."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        ordering: ClassVar[list[str]] = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Chat {str(self.id)[:8]}"


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "chat"
        ordering: ClassVar[list[str]] = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"
