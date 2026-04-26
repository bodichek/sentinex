"""Tenant-scoped data-access models: credentials, integrations, MCP audit, snapshots."""

from __future__ import annotations

import base64
import json
from typing import Any, ClassVar

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    # Derive a 32-byte urlsafe key from CRYPTOGRAPHY_KEY (truncate or pad).
    raw = settings.CRYPTOGRAPHY_KEY.encode("utf-8")
    padded = (raw + b"0" * 32)[:32]
    key = base64.urlsafe_b64encode(padded)
    return Fernet(key)


class Integration(models.Model):
    PROVIDER_GOOGLE_WORKSPACE = "google_workspace"
    PROVIDER_SLACK = "slack"
    PROVIDER_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (PROVIDER_GOOGLE_WORKSPACE, "Google Workspace"),
        (PROVIDER_SLACK, "Slack"),
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
