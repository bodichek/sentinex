"""Pipedrive ingest — BaseSync subclasses pulling raw records into normalized
scb_pipedrive_* tables with identity resolution and provenance.

Coexists with apps/connectors/pipedrive/sync.py (metric computation into
DataSnapshot). Both are needed: sync.py answers "what's the pipeline velocity"
on demand, ingest.py keeps full raw data for cross-system 360° queries.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.connectors._framework.base_sync import BaseSync, SyncContext
from apps.connectors._framework.identity_hook import (
    resolve_organization,
    resolve_person,
)
from apps.connectors._framework.rate_limit import TokenBucket
from apps.connectors.pipedrive.client import PipedriveClient
from apps.connectors.pipedrive.models import (
    ActivityType,
    DealStatus,
    ScbPipedriveActivity,
    ScbPipedriveDeal,
    ScbPipedriveOrganization,
    ScbPipedrivePerson,
)

logger = logging.getLogger(__name__)

PROVIDER = "pipedrive"
RATE_LIMIT = TokenBucket("pipedrive", capacity=80, refill_per_sec=40)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return parse_datetime(str(value))


# ---------------------------------------------------------------- Organizations
class PipedriveOrganizationSync(BaseSync):
    provider = PROVIDER
    resource = "organizations"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with PipedriveClient(self.integration) as client:
            yield from client.iter_organizations()

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        pipedrive_id = int(raw["id"])
        org_master = resolve_organization(
            source_system=PROVIDER,
            name=raw.get("name") or "",
            id_in_source=str(pipedrive_id),
        )
        obj, created = ScbPipedriveOrganization.objects.update_or_create(
            pipedrive_id=pipedrive_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": str(pipedrive_id),
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "organization": org_master,
                "name": raw.get("name") or "",
                "address": (raw.get("address") or "")[:512],
                "owner_pipedrive_user_id": (raw.get("owner_id") or {}).get("id")
                    if isinstance(raw.get("owner_id"), dict) else raw.get("owner_id"),
                "visible_to": int(raw["visible_to"]) if raw.get("visible_to") else None,
                "pipedrive_created_at": _parse_dt(raw.get("add_time")),
                "pipedrive_updated_at": _parse_dt(raw.get("update_time")),
            },
        )
        return "created" if created else "updated"


# --------------------------------------------------------------------- Persons
class PipedrivePersonSync(BaseSync):
    provider = PROVIDER
    resource = "persons"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with PipedriveClient(self.integration) as client:
            yield from client.iter_persons()

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        pipedrive_id = int(raw["id"])
        email = self._primary_email(raw)
        phone = self._primary_phone(raw)
        org_pipedrive_id = self._org_id(raw)
        master_org = None
        if org_pipedrive_id:
            mirror = ScbPipedriveOrganization.objects.filter(
                pipedrive_id=org_pipedrive_id
            ).only("organization_id").first()
            master_org = mirror.organization if mirror else None
        master_person = resolve_person(
            source_system=PROVIDER,
            email=email,
            full_name=raw.get("name") or "",
            phone=phone,
            person_id_in_source=str(pipedrive_id),
            organization=master_org,
        )
        obj, created = ScbPipedrivePerson.objects.update_or_create(
            pipedrive_id=pipedrive_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": str(pipedrive_id),
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "person": master_person,
                "organization": master_org,
                "pipedrive_org_id": org_pipedrive_id,
                "name": raw.get("name") or "",
                "primary_email": email or "",
                "primary_phone": phone or "",
                "owner_pipedrive_user_id": (raw.get("owner_id") or {}).get("id")
                    if isinstance(raw.get("owner_id"), dict) else raw.get("owner_id"),
                "pipedrive_created_at": _parse_dt(raw.get("add_time")),
                "pipedrive_updated_at": _parse_dt(raw.get("update_time")),
            },
        )
        return "created" if created else "updated"

    @staticmethod
    def _primary_email(raw: dict[str, Any]) -> str | None:
        emails = raw.get("email") or []
        if isinstance(emails, list):
            for e in emails:
                if isinstance(e, dict) and e.get("primary") and e.get("value"):
                    return str(e["value"])
            for e in emails:
                if isinstance(e, dict) and e.get("value"):
                    return str(e["value"])
        return None

    @staticmethod
    def _primary_phone(raw: dict[str, Any]) -> str | None:
        phones = raw.get("phone") or []
        if isinstance(phones, list):
            for p in phones:
                if isinstance(p, dict) and p.get("primary") and p.get("value"):
                    return str(p["value"])
            for p in phones:
                if isinstance(p, dict) and p.get("value"):
                    return str(p["value"])
        return None

    @staticmethod
    def _org_id(raw: dict[str, Any]) -> int | None:
        org = raw.get("org_id")
        if isinstance(org, dict):
            return int(org["value"]) if org.get("value") else None
        if isinstance(org, int):
            return org
        return None


# ----------------------------------------------------------------------- Deals
class PipedriveDealSync(BaseSync):
    provider = PROVIDER
    resource = "deals"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with PipedriveClient(self.integration) as client:
            yield from client.iter_deals(since=ctx.cursor_before or None)

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        pipedrive_id = int(raw["id"])
        org_pipedrive_id = self._org_id(raw)
        person_pipedrive_id = self._person_id(raw)

        master_org = None
        if org_pipedrive_id:
            org_mirror = ScbPipedriveOrganization.objects.filter(
                pipedrive_id=org_pipedrive_id
            ).only("organization_id").first()
            master_org = org_mirror.organization if org_mirror else None

        master_person = None
        if person_pipedrive_id:
            person_mirror = ScbPipedrivePerson.objects.filter(
                pipedrive_id=person_pipedrive_id
            ).only("person_id").first()
            master_person = person_mirror.person if person_mirror else None

        status = self._map_status(raw.get("status"))
        obj, created = ScbPipedriveDeal.objects.update_or_create(
            pipedrive_id=pipedrive_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": str(pipedrive_id),
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "organization": master_org,
                "person": master_person,
                "pipedrive_org_id": org_pipedrive_id,
                "pipedrive_person_id": person_pipedrive_id,
                "owner_pipedrive_user_id": (raw.get("user_id") or {}).get("id")
                    if isinstance(raw.get("user_id"), dict) else raw.get("user_id"),
                "title": (raw.get("title") or "")[:512],
                "value": raw.get("value") or 0,
                "currency": raw.get("currency") or "",
                "status": status,
                "stage_id": raw.get("stage_id"),
                "pipeline_id": raw.get("pipeline_id"),
                "expected_close_date": raw.get("expected_close_date") or None,
                "won_at": _parse_dt(raw.get("won_time")),
                "lost_at": _parse_dt(raw.get("lost_time")),
                "lost_reason": (raw.get("lost_reason") or "")[:255],
                "pipedrive_created_at": _parse_dt(raw.get("add_time")),
                "pipedrive_updated_at": _parse_dt(raw.get("update_time")),
            },
        )
        ctx.cursor_after = max(ctx.cursor_after, raw.get("update_time") or "")
        return "created" if created else "updated"

    @staticmethod
    def _org_id(raw: dict[str, Any]) -> int | None:
        org = raw.get("org_id")
        if isinstance(org, dict):
            return int(org["value"]) if org.get("value") else None
        if isinstance(org, int):
            return org
        return None

    @staticmethod
    def _person_id(raw: dict[str, Any]) -> int | None:
        p = raw.get("person_id")
        if isinstance(p, dict):
            return int(p["value"]) if p.get("value") else None
        if isinstance(p, int):
            return p
        return None

    @staticmethod
    def _map_status(value: Any) -> str:
        v = str(value or "open").lower()
        if v in {"won", "lost", "deleted"}:
            return v
        return DealStatus.OPEN


# ------------------------------------------------------------------- Activities
class PipedriveActivitySync(BaseSync):
    provider = PROVIDER
    resource = "activities"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with PipedriveClient(self.integration) as client:
            yield from client.iter_activities(days=60)

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        pipedrive_id = int(raw["id"])
        deal_id = raw.get("deal_id")
        org_id = raw.get("org_id")
        person_id = raw.get("person_id")

        deal_obj = None
        if deal_id:
            deal_obj = ScbPipedriveDeal.objects.filter(pipedrive_id=int(deal_id)).first()
        master_org = None
        if org_id:
            org_mirror = ScbPipedriveOrganization.objects.filter(
                pipedrive_id=int(org_id)
            ).only("organization_id").first()
            master_org = org_mirror.organization if org_mirror else None
        master_person = None
        if person_id:
            person_mirror = ScbPipedrivePerson.objects.filter(
                pipedrive_id=int(person_id)
            ).only("person_id").first()
            master_person = person_mirror.person if person_mirror else None

        atype = self._map_type(raw.get("type"))
        obj, created = ScbPipedriveActivity.objects.update_or_create(
            pipedrive_id=pipedrive_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": str(pipedrive_id),
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "deal": deal_obj,
                "organization": master_org,
                "person": master_person,
                "pipedrive_deal_id": deal_id,
                "pipedrive_org_id": org_id,
                "pipedrive_person_id": person_id,
                "activity_type": atype,
                "subject": (raw.get("subject") or "")[:512],
                "note": raw.get("note") or "",
                "due_date": raw.get("due_date") or None,
                "done": bool(raw.get("done")),
                "done_at": _parse_dt(raw.get("marked_as_done_time")),
                "owner_pipedrive_user_id": raw.get("user_id"),
                "pipedrive_created_at": _parse_dt(raw.get("add_time")),
                "pipedrive_updated_at": _parse_dt(raw.get("update_time")),
            },
        )
        return "created" if created else "updated"

    @staticmethod
    def _map_type(value: Any) -> str:
        v = str(value or "").lower()
        if v in ActivityType.values:
            return v
        return ActivityType.OTHER
