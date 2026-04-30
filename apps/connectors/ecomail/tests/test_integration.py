from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.ecomail.integration import EcomailIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert EcomailIntegration.provider == "ecomail"


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="ecomail").delete()
        integ = Integration.objects.create(provider="ecomail", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"api_key": "K"})
        cred.save()
        fake = MagicMock()
        fake.list_lists.return_value = [{"id": 1, "name": "All", "subscribers": 42}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.ecomail.integration.EcomailClient", return_value=fake):
            r = EcomailIntegration().call(integ, "lists.list", {})
        assert r.ok and r.data[0]["subscribers"] == 42
