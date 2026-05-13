"""Shared-schema identity registry: Organization, Person, PersonIdentity, roles.

Lives in SHARED_APPS so SCB employees can resolve a client across all tenants
before tenant context is set. Per-tenant business data (coaching, surveys,
challenges, finance) holds FKs to identity.Organization / identity.Person.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models
from django.utils import timezone


class IdentityType(models.TextChoices):
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"
    SLACK_ID = "slack_id", "Slack user ID"
    SLACK_HANDLE = "slack_handle", "Slack handle"
    PIPEDRIVE_PERSON_ID = "pipedrive_person_id", "Pipedrive person ID"
    PIPEDRIVE_ORG_ID = "pipedrive_org_id", "Pipedrive organization ID"
    FAPI_CUSTOMER_ID = "fapi_customer_id", "FAPI customer ID"
    BR_USER_ID = "br_user_id", "Business Review user ID"
    ZOOM_EMAIL = "zoom_email", "Zoom email"
    GOOGLE_ID = "google_id", "Google account ID"
    LINKEDIN_URL = "linkedin_url", "LinkedIn URL"
    ICO = "ico", "IČO"
    DIC = "dic", "DIČ"
    DOMAIN = "domain", "Email/web domain"


class SourceSystem(models.TextChoices):
    MANUAL = "manual", "Manual entry"
    PIPEDRIVE = "pipedrive", "Pipedrive"
    FAPI = "fapi", "FAPI"
    BR = "br", "Business Review"
    SLACK = "slack", "Slack"
    ZOOM = "zoom", "Zoom"
    GOOGLE = "google", "Google Workspace"
    MICROSOFT365 = "microsoft365", "Microsoft 365"
    MERK = "merk", "Merk"
    AI_MATCH = "ai_match", "AI matcher"


class PersonType(models.TextChoices):
    CLIENT = "client", "Klient"
    TEAM = "team", "Interní tým SCB"
    CONTACT = "contact", "Kontakt"
    VENDOR = "vendor", "Dodavatel"
    PROSPECT = "prospect", "Prospekt"
    OTHER = "other", "Jiné"


class OrganizationType(models.TextChoices):
    CLIENT = "client", "Klient SCB"
    PROSPECT = "prospect", "Prospekt"
    VENDOR = "vendor", "Dodavatel"
    PARTNER = "partner", "Partner"
    INTERNAL = "internal", "Interní (SCB)"
    OTHER = "other", "Jiné"


class Organization(models.Model):
    """A company / legal entity. Master record, separate from any source system."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name: models.CharField = models.CharField(max_length=255)
    legal_name: models.CharField = models.CharField(max_length=255, blank=True)
    org_type: models.CharField = models.CharField(
        max_length=32, choices=OrganizationType.choices, default=OrganizationType.CLIENT
    )
    ico: models.CharField = models.CharField(max_length=32, blank=True, db_index=True)
    dic: models.CharField = models.CharField(max_length=32, blank=True, db_index=True)
    primary_domain: models.CharField = models.CharField(max_length=255, blank=True, db_index=True)
    country: models.CharField = models.CharField(max_length=2, blank=True)
    confidence: models.FloatField = models.FloatField(default=1.0)
    merged_into: models.ForeignKey = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from"
    )

    # tenant link: when org becomes a paying client a Tenant schema is created
    tenant: models.OneToOneField = models.OneToOneField(
        "core.Tenant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organization",
    )

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        indexes: ClassVar = [
            models.Index(fields=["org_type"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return str(self.name)


class Person(models.Model):
    """A human. Master record, identifiers attached via PersonIdentity."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name: models.CharField = models.CharField(max_length=255)
    first_name: models.CharField = models.CharField(max_length=128, blank=True)
    last_name: models.CharField = models.CharField(max_length=128, blank=True)
    primary_email: models.EmailField = models.EmailField(blank=True, db_index=True)
    person_type: models.CharField = models.CharField(
        max_length=32, choices=PersonType.choices, default=PersonType.CONTACT
    )
    confidence: models.FloatField = models.FloatField(default=1.0)
    merged_into: models.ForeignKey = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from"
    )

    # convenience link to Sentinex auth user (if this person logs in)
    user: models.OneToOneField = models.OneToOneField(
        "core.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="person",
    )

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        indexes: ClassVar = [
            models.Index(fields=["person_type"]),
            models.Index(fields=["display_name"]),
        ]

    def __str__(self) -> str:
        return self.display_name or self.primary_email or str(self.id)


class PersonIdentity(models.Model):
    """One identifier (email, slack_id, pipedrive_id…) for a Person."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person: models.ForeignKey = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="identities"
    )
    identity_type: models.CharField = models.CharField(max_length=32, choices=IdentityType.choices)
    identity_value: models.CharField = models.CharField(max_length=512)
    source_system: models.CharField = models.CharField(
        max_length=32, choices=SourceSystem.choices, default=SourceSystem.MANUAL
    )
    verified: models.BooleanField = models.BooleanField(default=False)
    confidence: models.FloatField = models.FloatField(default=1.0)
    first_seen: models.DateTimeField = models.DateTimeField(default=timezone.now)
    last_seen: models.DateTimeField = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["identity_type", "identity_value"],
                name="uniq_identity_type_value",
            ),
        ]
        indexes: ClassVar = [
            models.Index(fields=["identity_type"]),
            models.Index(fields=["identity_value"]),
        ]

    def __str__(self) -> str:
        return f"{self.identity_type}={self.identity_value}"


class OrganizationIdentity(models.Model):
    """Identifier for an Organization (pipedrive_org_id, fapi_customer_id, ICO…)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization: models.ForeignKey = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="identities"
    )
    identity_type: models.CharField = models.CharField(max_length=32, choices=IdentityType.choices)
    identity_value: models.CharField = models.CharField(max_length=512)
    source_system: models.CharField = models.CharField(
        max_length=32, choices=SourceSystem.choices, default=SourceSystem.MANUAL
    )
    verified: models.BooleanField = models.BooleanField(default=False)
    confidence: models.FloatField = models.FloatField(default=1.0)
    first_seen: models.DateTimeField = models.DateTimeField(default=timezone.now)
    last_seen: models.DateTimeField = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["identity_type", "identity_value"],
                name="uniq_org_identity_type_value",
            ),
        ]
        indexes: ClassVar = [
            models.Index(fields=["identity_type"]),
            models.Index(fields=["identity_value"]),
        ]

    def __str__(self) -> str:
        return f"{self.identity_type}={self.identity_value}"


class PersonRole(models.TextChoices):
    CEO = "ceo", "CEO"
    COO = "coo", "COO"
    CFO = "cfo", "CFO"
    CTO = "cto", "CTO"
    OWNER = "owner", "Majitel"
    EMPLOYEE = "employee", "Zaměstnanec"
    BOARD = "board", "Člen představenstva"
    CONTACT = "contact", "Kontaktní osoba"
    COACH = "coach", "Kouč (SCB)"
    SALES = "sales", "Sales (SCB)"
    OTHER = "other", "Jiné"


class PersonOrganizationRole(models.Model):
    """Person ↔ Organization with a role and validity window (bi-temporal)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person: models.ForeignKey = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="org_roles"
    )
    organization: models.ForeignKey = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="person_roles"
    )
    role: models.CharField = models.CharField(max_length=32, choices=PersonRole.choices)
    is_primary: models.BooleanField = models.BooleanField(default=False)
    valid_from: models.DateField = models.DateField(null=True, blank=True)
    valid_to: models.DateField = models.DateField(null=True, blank=True)
    source_system: models.CharField = models.CharField(
        max_length=32, choices=SourceSystem.choices, default=SourceSystem.MANUAL
    )

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        indexes: ClassVar = [
            models.Index(fields=["role"]),
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self) -> str:
        return f"{self.person} @ {self.organization} ({self.role})"


class MatchMethod(models.TextChoices):
    EMAIL_EXACT = "email_exact", "Email exact match"
    IDENTITY_EXACT = "identity_exact", "Identity exact match"
    NAME_DOMAIN_FUZZY = "name_domain_fuzzy", "Name + domain fuzzy"
    NAME_COMPANY_FUZZY = "name_company_fuzzy", "Name + company fuzzy"
    AI_MATCH = "ai_match", "AI matcher"
    SLACK_LOOKUP = "slack_lookup", "Slack lookupByEmail"
    MANUAL = "manual", "Manual"


class PersonMergeLog(models.Model):
    """Audit trail of Person merges. Allows manual unmerge via undo_token."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person_a: models.UUIDField = models.UUIDField()
    person_b: models.UUIDField = models.UUIDField()
    merged_into: models.ForeignKey = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, related_name="merge_events"
    )
    matched_by: models.CharField = models.CharField(max_length=32, choices=MatchMethod.choices)
    confidence: models.FloatField = models.FloatField(default=1.0)
    matched_by_user: models.ForeignKey = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    matched_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    notes: models.TextField = models.TextField(blank=True)
    snapshot: models.JSONField = models.JSONField(default=dict, blank=True)
    undo_token: models.UUIDField = models.UUIDField(default=uuid.uuid4)

    def __str__(self) -> str:
        return f"merge {self.person_a} + {self.person_b} → {self.merged_into}"
