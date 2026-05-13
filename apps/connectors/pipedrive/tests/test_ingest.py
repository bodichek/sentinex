from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors._framework.models import SyncStatus
from apps.connectors.pipedrive.ingest import (
    PipedriveDealSync,
    PipedriveOrganizationSync,
)
from apps.connectors.pipedrive.models import (
    ScbPipedriveDeal,
    ScbPipedriveOrganization,
)
from apps.data_access.models import Credential, Integration
from apps.identity.models import Organization


@contextmanager
def _tenant():
    with schema_context("test_tenant"):
        yield


@pytest.fixture
def integration(db) -> Integration:
    with _tenant():
        integ = Integration.objects.create(provider="pipedrive", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "fake", "refresh_token": "fake",
                         "api_domain": "https://api.pipedrive.com"})
        cred.save()
    return integ


@pytest.mark.django_db
def test_organization_sync_creates_master_and_mirror(integration: Integration) -> None:
    sample = [
        {"id": 101, "name": "ACME s.r.o.", "address": "Praha 1",
         "owner_id": {"id": 7, "name": "petr"}, "visible_to": "3",
         "add_time": "2026-04-01 09:00:00", "update_time": "2026-04-02 10:00:00"},
    ]
    with _tenant(), patch("apps.connectors.pipedrive.ingest.PipedriveClient") as MockClient:
        MockClient.return_value.__enter__.return_value.iter_organizations.return_value = sample
        outcome = PipedriveOrganizationSync(integration).run()
    assert outcome.status == SyncStatus.COMPLETED
    assert outcome.created == 1
    with _tenant():
        mirror = ScbPipedriveOrganization.objects.get(pipedrive_id=101)
        master_id = mirror.organization_id
        assert mirror.name == "ACME s.r.o."
        assert master_id is not None
        assert mirror.raw_payload["id"] == 101
        assert mirror.source_system == "pipedrive"
    assert Organization.objects.filter(id=master_id).exists()


@pytest.mark.django_db
def test_deal_sync_links_via_organization_mirror(integration: Integration) -> None:
    # Pre-seed organization mirror so the deal can link to it
    PipedriveOrganizationSync_sample = [
        {"id": 101, "name": "ACME", "address": "", "owner_id": None,
         "visible_to": "3", "add_time": "2026-04-01 09:00:00",
         "update_time": "2026-04-01 09:00:00"},
    ]
    with _tenant(), patch("apps.connectors.pipedrive.ingest.PipedriveClient") as MockClient:
        MockClient.return_value.__enter__.return_value.iter_organizations.return_value = (
            PipedriveOrganizationSync_sample
        )
        PipedriveOrganizationSync(integration).run()

    deals = [
        {"id": 555, "title": "Founder program",
         "value": 99000, "currency": "CZK",
         "status": "open", "stage_id": 4, "pipeline_id": 1,
         "org_id": {"value": 101, "name": "ACME"},
         "person_id": None,
         "user_id": {"id": 7, "name": "petr"},
         "add_time": "2026-04-10 08:00:00",
         "update_time": "2026-04-12 12:00:00"},
    ]
    with _tenant(), patch("apps.connectors.pipedrive.ingest.PipedriveClient") as MockClient:
        MockClient.return_value.__enter__.return_value.iter_deals.return_value = deals
        outcome = PipedriveDealSync(integration).run()

    assert outcome.status == SyncStatus.COMPLETED
    with _tenant():
        deal = ScbPipedriveDeal.objects.get(pipedrive_id=555)
        assert deal.title == "Founder program"
        assert deal.value == 99000
        assert deal.currency == "CZK"
        assert deal.status == "open"
        assert deal.organization_id is not None  # linked via mirror lookup
        assert deal.source_system == "pipedrive"
        assert deal.raw_payload["id"] == 555


@pytest.mark.django_db
def test_deal_sync_records_errors_without_killing_run(integration: Integration) -> None:
    deals = [
        {"id": 1, "title": "ok", "value": 100, "currency": "CZK",
         "status": "open", "add_time": "2026-04-01 09:00:00",
         "update_time": "2026-04-01 09:00:00"},
        {"id": "BROKEN"},  # int() will raise on id
    ]
    with _tenant(), patch("apps.connectors.pipedrive.ingest.PipedriveClient") as MockClient:
        MockClient.return_value.__enter__.return_value.iter_deals.return_value = deals
        outcome = PipedriveDealSync(integration).run()
    assert outcome.status == SyncStatus.PARTIAL
    assert outcome.created == 1
    assert outcome.errors == 1
