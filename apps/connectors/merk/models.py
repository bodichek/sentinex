"""Merk enrichment cache — populated by on-demand lookup, not periodic batch.

A row exists for every IČO we've looked up; refresh policy lives in the
service layer (currently: refresh if older than 30 days).
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

from apps.connectors._framework.provenance import ProvenanceMixin


class ScbMerkCompany(ProvenanceMixin):
    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ico: models.CharField = models.CharField(max_length=32, unique=True, db_index=True)
    organization: models.ForeignKey = models.ForeignKey(
        "identity.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    dic: models.CharField = models.CharField(max_length=32, blank=True)
    name: models.CharField = models.CharField(max_length=255)
    legal_form: models.CharField = models.CharField(max_length=64, blank=True)
    status: models.CharField = models.CharField(max_length=32, blank=True)
    nace_codes: models.JSONField = models.JSONField(default=list, blank=True)
    employee_count_range: models.CharField = models.CharField(max_length=32, blank=True)
    turnover_range: models.CharField = models.CharField(max_length=32, blank=True)
    last_known_turnover: models.DecimalField = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    turnover_year: models.IntegerField = models.IntegerField(null=True, blank=True)
    profit_last: models.DecimalField = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    profit_year: models.IntegerField = models.IntegerField(null=True, blank=True)
    rating: models.CharField = models.CharField(max_length=16, blank=True)
    rating_breakdown: models.JSONField = models.JSONField(default=dict, blank=True)
    address: models.JSONField = models.JSONField(default=dict, blank=True)
    website: models.CharField = models.CharField(max_length=255, blank=True)
    contacts_summary: models.JSONField = models.JSONField(default=dict, blank=True)

    class Meta(ProvenanceMixin.Meta):
        indexes: ClassVar = [
            *ProvenanceMixin.Meta.indexes,
            models.Index(fields=["ico"]),
        ]
