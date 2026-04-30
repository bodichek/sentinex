"""Trello integration tests — mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.trello.integration import TrelloIntegration
from apps.connectors.trello.sync import _summarise_cards
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert TrelloIntegration.provider == "trello"


def test_exchange_code_parses_pasted_pair() -> None:
    spec = TrelloIntegration().exchange_code("KEY:TOKEN", "")
    assert spec == {"api_key": "KEY", "token": "TOKEN"}


def test_summarise_cards_buckets_open_closed_overdue() -> None:
    cards = [
        {"closed": False, "due": None, "dueComplete": False},
        {"closed": True, "due": None, "dueComplete": False},
        {"closed": False, "due": "2020-01-01T00:00:00.000Z", "dueComplete": False},
        {"closed": False, "due": "2099-12-31T00:00:00.000Z", "dueComplete": True},
    ]
    s = _summarise_cards(cards)
    assert s["total"] == 4
    assert s["closed"] == 1
    assert s["open"] == 3
    assert s["overdue"] == 1
    assert s["completed"] == 1


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="trello").delete()
        integ = Integration.objects.create(provider="trello", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"api_key": "K", "token": "T"})
        cred.save()

        fake = MagicMock()
        fake.list_boards.return_value = [{"id": "1", "name": "Roadmap"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None

        with patch(
            "apps.connectors.trello.integration.TrelloClient", return_value=fake
        ):
            result = TrelloIntegration().call(integ, "boards.list", {})
        assert result.ok
        assert result.data == [{"id": "1", "name": "Roadmap"}]
