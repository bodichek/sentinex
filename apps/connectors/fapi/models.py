"""Normalized FAPI ingest models — populated by apps.connectors.fapi.ingest.

FAPI = Scaleupboard's invoicing system. Customers map to identity.Organization
(via ICO when available, fallback to email/name). Invoices link to those
organizations and carry provenance.

Exact field names follow FAPI conventions but are intentionally loose — when
real FAPI access is available, schema can be tightened without breaking
ingest (raw_payload retains everything).
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

from apps.connectors._framework.provenance import ProvenanceMixin


class ScbFapiCustomer(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fapi_id: models.CharField = models.CharField(max_length=64, unique=True)
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    name: models.CharField = models.CharField(max_length=255)
    ico: models.CharField = models.CharField(max_length=32, blank=True, db_index=True)
    dic: models.CharField = models.CharField(max_length=32, blank=True)
    email: models.EmailField = models.EmailField(blank=True)
    phone: models.CharField = models.CharField(max_length=64, blank=True)
    address: models.JSONField = models.JSONField(default=dict, blank=True)
    fapi_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    fapi_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["fapi_id"]),
            models.Index(fields=["ico"]),
        ]


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PARTIAL = "partial", "Partial"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"
    UNKNOWN = "unknown", "Unknown"


class ScbFapiInvoice(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fapi_id: models.CharField = models.CharField(max_length=64, unique=True)
    number: models.CharField = models.CharField(max_length=64, blank=True, db_index=True)
    customer: models.ForeignKey = models.ForeignKey(
        ScbFapiCustomer, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    amount: models.DecimalField = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_amount: models.DecimalField = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency: models.CharField = models.CharField(max_length=8, default="CZK")
    status: models.CharField = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.UNKNOWN
    )
    issued_at: models.DateField = models.DateField(null=True, blank=True)
    due_at: models.DateField = models.DateField(null=True, blank=True)
    paid_at: models.DateField = models.DateField(null=True, blank=True)
    items: models.JSONField = models.JSONField(default=list, blank=True)
    fapi_created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    fapi_updated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["fapi_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["due_at"]),
        ]
