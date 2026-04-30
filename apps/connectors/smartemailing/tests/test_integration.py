"""SmartEmailing integration tests — mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.smartemailing.integration import SmartEmailingIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert SmartEmailingIntegration.provider == "smartemailing"


def test_exchange_code_parses_pasted_secret() -> None:
    spec = SmartEmailingIntegration().exchange_code("user@acme.cz:KEY123", "")
    assert spec == {"username": "user@acme.cz", "api_key": "KEY123"}


def test_exchange_code_rejects_malformed() -> None:
    with pytest.raises(ValueError):
        SmartEmailingIntegration().exchange_code("nope-no-colon", "")


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="smartemailing").delete()
        integ = Integration.objects.create(provider="smartemailing", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"username": "u", "api_key": "k"})
        cred.save()

        fake = MagicMock()
        fake.list_contactlists.return_value = [{"id": 1, "name": "All"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None

        with patch(
            "apps.connectors.smartemailing.integration.SmartEmailingClient",
            return_value=fake,
        ):
            result = SmartEmailingIntegration().call(integ, "contactlists.list", {})
        assert result.ok
        assert result.data == [{"id": 1, "name": "All"}]
