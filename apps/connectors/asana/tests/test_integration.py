"""Asana smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.asana import oauth
from apps.connectors.asana.integration import AsanaIntegration
from apps.connectors.asana.sync import _summarise_tasks
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert AsanaIntegration.provider == "asana"


@override_settings(ASANA_CLIENT_ID="cid", ASANA_CLIENT_SECRET="csec")
def test_authorization_url_includes_state() -> None:
    url = oauth.authorization_url("STATE", "https://app/cb")
    assert "client_id=cid" in url and "state=STATE" in url


def test_summarise_tasks_open_completed_overdue() -> None:
    tasks = [
        {"completed": True, "due_on": None},
        {"completed": False, "due_on": "2099-12-31"},
        {"completed": False, "due_on": "2020-01-01"},
    ]
    s = _summarise_tasks(tasks)
    assert s["total"] == 3
    assert s["completed"] == 1
    assert s["open"] == 2
    assert s["overdue"] == 1


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="asana").delete()
        integ = Integration.objects.create(provider="asana", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "AT", "refresh_token": "RT"})
        cred.save()
        fake = MagicMock()
        fake.list_workspaces.return_value = [{"gid": "1", "name": "Acme"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.asana.integration.AsanaClient", return_value=fake):
            r = AsanaIntegration().call(integ, "workspaces.list", {})
        assert r.ok and r.data[0]["name"] == "Acme"
