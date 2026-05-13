"""Normalized Slack ingest models — workspace, channels (opt-in), messages.

Slack user IDs are mapped to identity.PersonIdentity(slack_id) at ingest time
so cross-system queries (FAPI invoice → Slack mentions → BR coaching session)
work via identity.Person FK.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

from apps.connectors._framework.provenance import ProvenanceMixin


class ScbSlackWorkspace(models.Model):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_id: models.CharField = models.CharField(max_length=32, unique=True)
    name: models.CharField = models.CharField(max_length=255)
    domain: models.CharField = models.CharField(max_length=128, blank=True)
    integration: models.OneToOneField = models.OneToOneField(
        "data_access.Integration",
        on_delete=models.CASCADE,
        related_name="slack_workspace",
    )
    is_active: models.BooleanField = models.BooleanField(default=True)
    last_synced_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    raw_payload: models.JSONField = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.team_id})"


class ScbSlackChannel(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        ScbSlackWorkspace, on_delete=models.CASCADE, related_name="channels"
    )
    slack_channel_id: models.CharField = models.CharField(max_length=32, unique=True)
    name: models.CharField = models.CharField(max_length=128)
    purpose: models.TextField = models.TextField(blank=True)
    topic: models.TextField = models.TextField(blank=True)
    is_private: models.BooleanField = models.BooleanField(default=False)
    is_archived: models.BooleanField = models.BooleanField(default=False)
    is_tracked: models.BooleanField = models.BooleanField(default=False, db_index=True)
    member_count: models.IntegerField = models.IntegerField(default=0)
    last_message_synced_ts: models.CharField = models.CharField(max_length=32, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["slack_channel_id"]),
        ]


class ScbSlackMessage(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel: models.ForeignKey = models.ForeignKey(
        ScbSlackChannel, on_delete=models.CASCADE, related_name="messages"
    )
    ts: models.CharField = models.CharField(max_length=32)
    thread_ts: models.CharField = models.CharField(max_length=32, blank=True)
    slack_user_id: models.CharField = models.CharField(max_length=32, blank=True)
    person: models.ForeignKey = models.ForeignKey(
        "identity.Person", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    text: models.TextField = models.TextField(blank=True)
    has_attachments: models.BooleanField = models.BooleanField(default=False)
    reactions: models.JSONField = models.JSONField(default=list, blank=True)
    posted_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["channel", "ts"], name="uniq_slack_channel_ts"
            ),
        ]
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["channel", "-posted_at"]),
            models.Index(fields=["thread_ts"]),
        ]
