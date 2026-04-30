from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.caflou.integration import CaflouIntegration
from apps.connectors.caflou.sync import _count
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert CaflouIntegration.provider == "caflou"


def test_count_understands_common_payload_shapes() -> None:
    assert _count({"total": 7}) == 7
    assert _count({"meta": {"total": 4}}) == 4
    assert _count({"data": [1, 2, 3]}) == 3
    assert _count([1, 2]) == 2
    assert _count({}) == 0


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="caflou").delete()
        integ = Integration.objects.create(provider="caflou", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"api_token": "T"})
        cred.save()

        fake = MagicMock()
        fake.list_projects.return_value = {"data": [{"id": 1}]}
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.caflou.integration.CaflouClient", return_value=fake):
            r = CaflouIntegration().call(integ, "projects.list", {})
        assert r.ok and r.data == {"data": [{"id": 1}]}
