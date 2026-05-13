"""Normalized Pipedrive ingest models — populated by apps.connectors.pipedrive.ingest.

These tables hold raw Pipedrive records with provenance + FKs to identity.Person /
identity.Organization. Aggregated metrics live elsewhere (apps.data_access.DataSnapshot
written by apps.connectors.pipedrive.sync) — these two paths coexist intentionally.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

from apps.connectors._framework.provenance import ProvenanceMixin


class ScbPipedriveOrganization(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipedrive_id: models.IntegerField = models.IntegerField(unique=True)
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    name: models.CharField = models.CharField(max_length=255)
    address: models.CharField = models.CharField(max_length=512, blank=True)
    owner_pipedrive_user_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    owner_person: models.ForeignKey = models.ForeignKey(
        "identity.Person", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    visible_to: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    pipedrive_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["pipedrive_id"]),
        ]


class ScbPipedrivePerson(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipedrive_id: models.IntegerField = models.IntegerField(unique=True)
    person: models.ForeignKey = models.ForeignKey(
        "identity.Person", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pipedrive_org_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    name: models.CharField = models.CharField(max_length=255)
    primary_email: models.EmailField = models.EmailField(blank=True)
    primary_phone: models.CharField = models.CharField(max_length=64, blank=True)
    owner_pipedrive_user_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    pipedrive_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["pipedrive_id"]),
            models.Index(fields=["primary_email"]),
        ]


class DealStatus(models.TextChoices):
    OPEN = "open", "Open"
    WON = "won", "Won"
    LOST = "lost", "Lost"
    DELETED = "deleted", "Deleted"


class ScbPipedriveDeal(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipedrive_id: models.IntegerField = models.IntegerField(unique=True)
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    person: models.ForeignKey = models.ForeignKey(
        "identity.Person", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pipedrive_org_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_person_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    owner_pipedrive_user_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    title: models.CharField = models.CharField(max_length=512)
    value: models.DecimalField = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency: models.CharField = models.CharField(max_length=8, blank=True)
    status: models.CharField = models.CharField(
        max_length=16, choices=DealStatus.choices, default=DealStatus.OPEN
    )
    stage_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipeline_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    expected_close_date: models.DateField = models.DateField(null=True, blank=True)
    won_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    lost_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    lost_reason: models.CharField = models.CharField(max_length=255, blank=True)
    pipedrive_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    pipedrive_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["pipedrive_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["organization", "status"]),
        ]


class ActivityType(models.TextChoices):
    CALL = "call", "Call"
    MEETING = "meeting", "Meeting"
    EMAIL = "email", "Email"
    TASK = "task", "Task"
    LUNCH = "lunch", "Lunch"
    DEADLINE = "deadline", "Deadline"
    OTHER = "other", "Other"


class ScbPipedriveActivity(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipedrive_id: models.IntegerField = models.IntegerField(unique=True)
    deal: models.ForeignKey = models.ForeignKey(
        ScbPipedriveDeal, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities"
    )
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    person: models.ForeignKey = models.ForeignKey(
        "identity.Person", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pipedrive_deal_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_org_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_person_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    activity_type: models.CharField = models.CharField(
        max_length=16, choices=ActivityType.choices, default=ActivityType.OTHER
    )
    subject: models.CharField = models.CharField(max_length=512, blank=True)
    note: models.TextField = models.TextField(blank=True)
    due_date: models.DateField = models.DateField(null=True, blank=True)
    done: models.BooleanField = models.BooleanField(default=False)
    done_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    owner_pipedrive_user_id: models.IntegerField = models.IntegerField(null=True, blank=True)
    pipedrive_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    pipedrive_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["pipedrive_id"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["done"]),
        ]
