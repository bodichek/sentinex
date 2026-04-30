"""Tenant-scoped data-access models: credentials, integrations, MCP audit, snapshots."""

from __future__ import annotations

import base64
import json
from typing import Any, ClassVar

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


_INSECURE_DEFAULT_KEY = "insecure-dev-cryptography-key-change"
_MIN_KEY_LENGTH = 32


def _fernet() -> Fernet:
    raw_text = settings.CRYPTOGRAPHY_KEY
    if not settings.DEBUG and raw_text == _INSECURE_DEFAULT_KEY:
        raise RuntimeError(
            "CRYPTOGRAPHY_KEY is set to the insecure development default; "
            "set a strong value in the environment before running outside DEBUG."
        )
    if len(raw_text) < _MIN_KEY_LENGTH:
        raise RuntimeError(
            f"CRYPTOGRAPHY_KEY must be at least {_MIN_KEY_LENGTH} characters; "
            f"got {len(raw_text)}."
        )
    raw = raw_text.encode("utf-8")[:_MIN_KEY_LENGTH]
    return Fernet(base64.urlsafe_b64encode(raw))


class Integration(models.Model):
    PROVIDER_GOOGLE_WORKSPACE = "google_workspace"
    PROVIDER_GOOGLE_WORKSPACE_DWD = "google_workspace_dwd"
    PROVIDER_SLACK = "slack"
    PROVIDER_SMARTEMAILING = "smartemailing"
    PROVIDER_PIPEDRIVE = "pipedrive"
    PROVIDER_CANVA = "canva"
    PROVIDER_TRELLO = "trello"
    PROVIDER_RAYNET = "raynet"
    PROVIDER_CAFLOU = "caflou"
    PROVIDER_ECOMAIL = "ecomail"
    PROVIDER_FAPI = "fapi"
    PROVIDER_MICROSOFT365 = "microsoft365"
    PROVIDER_SALESFORCE = "salesforce"
    PROVIDER_ASANA = "asana"
    PROVIDER_BASECAMP = "basecamp"
    PROVIDER_MAILCHIMP = "mailchimp"
    PROVIDER_CALENDLY = "calendly"
    PROVIDER_HUBSPOT = "hubspot"
    PROVIDER_JIRA = "jira"
    PROVIDER_NOTION = "notion"
    PROVIDER_DROPBOX = "dropbox"
    PROVIDER_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (PROVIDER_GOOGLE_WORKSPACE, "Google Workspace (per-user OAuth)"),
        (PROVIDER_GOOGLE_WORKSPACE_DWD, "Google Workspace (Domain-Wide Delegation)"),
        (PROVIDER_SLACK, "Slack"),
        (PROVIDER_SMARTEMAILING, "SmartEmailing"),
        (PROVIDER_PIPEDRIVE, "Pipedrive"),
        (PROVIDER_CANVA, "Canva (MCP)"),
        (PROVIDER_TRELLO, "Trello"),
        (PROVIDER_RAYNET, "Raynet CRM"),
        (PROVIDER_CAFLOU, "Caflou"),
        (PROVIDER_ECOMAIL, "Ecomail"),
        (PROVIDER_FAPI, "FAPI"),
        (PROVIDER_MICROSOFT365, "Microsoft 365 (mail + Teams + OneDrive)"),
        (PROVIDER_SALESFORCE, "Salesforce"),
        (PROVIDER_ASANA, "Asana"),
        (PROVIDER_BASECAMP, "Basecamp"),
        (PROVIDER_MAILCHIMP, "Mailchimp"),
        (PROVIDER_CALENDLY, "Calendly"),
        (PROVIDER_HUBSPOT, "HubSpot"),
        (PROVIDER_JIRA, "Jira (Atlassian)"),
        (PROVIDER_NOTION, "Notion (MCP)"),
        (PROVIDER_DROPBOX, "Dropbox (MCP)"),
    ]

    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=False)
    connected_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    last_sync_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "data_access"
        unique_together = ("provider",)

    def __str__(self) -> str:
        return f"{self.provider} ({'on' if self.is_active else 'off'})"


class Credential(models.Model):
    """OAuth credentials for an integration. `oauth_tokens` is encrypted at rest."""

    integration = models.OneToOneField(
        Integration, on_delete=models.CASCADE, related_name="credential"
    )
    encrypted_tokens = models.BinaryField()
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "data_access"

    def __str__(self) -> str:
        return f"Credential for {self.integration_id}"

    def set_tokens(self, tokens: dict[str, Any]) -> None:
        self.encrypted_tokens = _fernet().encrypt(json.dumps(tokens).encode("utf-8"))

    def get_tokens(self) -> dict[str, Any]:
        try:
            raw = _fernet().decrypt(bytes(self.encrypted_tokens))
        except InvalidToken as exc:
            raise ValueError("Credential decryption failed") from exc
        result: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return result


class MCPCall(models.Model):
    """Audit row for each MCP Gateway invocation."""

    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="calls")
    tool = models.CharField(max_length=100)
    params_hash = models.CharField(max_length=64)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=200, blank=True)
    latency_ms = models.IntegerField(default=0)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "data_access"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["integration", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tool} ok={self.ok}"


class ManualKPI(models.Model):
    """CEO-entered KPI values used until accounting integrations land."""

    name = models.CharField(max_length=80, db_index=True)
    value = models.DecimalField(max_digits=18, decimal_places=2)
    unit = models.CharField(max_length=20, default="CZK")
    period_end = models.DateField()
    notes = models.TextField(blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "data_access"
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["name", "-period_end"])]
        ordering: ClassVar[list[str]] = ["-period_end", "name"]

    def __str__(self) -> str:
        return f"{self.name}={self.value} {self.unit} @ {self.period_end}"


class DataSnapshot(models.Model):
    """Computed metrics produced by a sync pipeline."""

    source = models.CharField(max_length=40)
    period_start = models.DateField()
    period_end = models.DateField()
    metrics = models.JSONField(default=dict)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "data_access"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["source", "-period_end"]),
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.period_start}..{self.period_end}"


class WorkspaceDocument(models.Model):
    """Metadata for a single Google Workspace artifact (Drive file, Gmail thread, etc.)."""

    SOURCE_DRIVE = "drive"
    SOURCE_GMAIL = "gmail"
    SOURCE_CALENDAR = "calendar"
    SOURCE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (SOURCE_DRIVE, "Drive"),
        (SOURCE_GMAIL, "Gmail"),
        (SOURCE_CALENDAR, "Calendar"),
    ]

    STATUS_PENDING = "pending"
    STATUS_EXTRACTED = "extracted"
    STATUS_INDEXED = "indexed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (STATUS_PENDING, "Pending"),
        (STATUS_EXTRACTED, "Extracted"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    external_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=512, blank=True)
    mime_type = models.CharField(max_length=128, blank=True)
    owner_email = models.EmailField(blank=True)
    web_view_link = models.URLField(max_length=1024, blank=True)
    modified_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    text_content = models.TextField(blank=True)
    text_truncated = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=500, blank=True)
    extracted_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    indexed_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "data_access"
        unique_together = ("source", "external_id")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["owner_email"]),
            models.Index(fields=["-modified_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.external_id} {self.title[:40]}"


class IngestionCursor(models.Model):
    """Per-source incremental sync cursor (Drive changes pageToken, Gmail historyId, etc.)."""

    source = models.CharField(max_length=40, unique=True)
    cursor = models.CharField(max_length=255, blank=True)
    last_full_sync_at: models.DateTimeField[None, None] = models.DateTimeField(
        null=True, blank=True
    )
    last_incremental_sync_at: models.DateTimeField[None, None] = models.DateTimeField(
        null=True, blank=True
    )
    files_total = models.IntegerField(default=0)
    files_indexed = models.IntegerField(default=0)
    files_failed = models.IntegerField(default=0)

    class Meta:
        app_label = "data_access"

    def __str__(self) -> str:
        return f"cursor[{self.source}]={self.cursor[:20]}"


class KnowledgeChunk(models.Model):
    """Chunked + embedded slice of a WorkspaceDocument used for RAG.

    Table is created via raw SQL in a migration so the pgvector extension can be
    checked/created first; ``managed = False`` keeps Django from emitting CREATE
    TABLE through the standard migration codegen.
    """

    id = models.UUIDField(primary_key=True)
    document = models.ForeignKey(
        WorkspaceDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
        db_constraint=False,
    )
    chunk_index = models.IntegerField()
    text = models.TextField()
    token_count = models.IntegerField(default=0)
    embedding = models.JSONField(null=True, blank=True)  # placeholder for type stubs
    metadata = models.JSONField(default=dict, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "data_access"
        managed = False
        db_table = "data_access_knowledgechunk"

    def __str__(self) -> str:
        return f"chunk[{self.document_id}#{self.chunk_index}] {self.text[:40]}"
