"""Calendly smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.calendly import oauth
from apps.connectors.calendly.integration import CalendlyIntegration
from apps.connectors.calendly.sync import _summarise_events
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert CalendlyIntegration.provider == "calendly"


@override_settings(CALENDLY_CLIENT_ID="cid", CALENDLY_CLIENT_SECRET="csec")
def test_authorization_url_includes_state() -> None:
    url = oauth.authorization_url("STATE", "https://app/cb")
    assert "client_id=cid" in url and "state=STATE" in url


def test_summarise_events_counts_upcoming_and_status() -> None:
    events = [
        {"status": "active", "start_time": "2099-01-01T10:00:00Z"},
        {"status": "active", "start_time": "2020-01-01T10:00:00Z"},
        {"status": "canceled", "start_time": None},
    ]
    s = _summarise_events(events)
    assert s["total"] == 3
    assert s["upcoming"] == 1
    assert s["by_status"] == {"active": 2, "canceled": 1}


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="calendly").delete()
        integ = Integration.objects.create(provider="calendly", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens(
            {"access_token": "AT", "refresh_token": "RT", "owner": "https://api.calendly.com/users/abc"}
        )
        cred.save()
        fake = MagicMock()
        fake.list_event_types.return_value = [{"uri": "https://api.calendly.com/event_types/x"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch(
            "apps.connectors.calendly.integration.CalendlyClient", return_value=fake
        ):
            r = CalendlyIntegration().call(integ, "event_types.list", {})
        assert r.ok and len(r.data) == 1
