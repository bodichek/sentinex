"""Unit tests for shared paste-key setup helpers."""

from __future__ import annotations

import pytest
from django_tenants.utils import schema_context

from apps.connectors._setup import (
    clear_setup_attempt,
    last_setup_context,
    record_setup_attempt,
)
from apps.data_access.models import Integration


def test_last_setup_context_for_missing_integration_returns_empty() -> None:
    ctx = last_setup_context(None)
    assert ctx == {"last_error": "", "last_at": "", "last_fields": {}}


@pytest.mark.django_db(transaction=True)
def test_record_then_render_round_trip() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="raynet").delete()
        integ = Integration.objects.create(provider="raynet", is_active=False)
        record_setup_attempt(
            integ,
            fields={"instance": "acme", "username": "u@firma.cz"},
            error="HTTP 401: bad token",
        )
        ctx = last_setup_context(integ)
        assert ctx["last_error"] == "HTTP 401: bad token"
        assert ctx["last_fields"] == {"instance": "acme", "username": "u@firma.cz"}
        assert ctx["last_at"]  # ISO timestamp string

        clear_setup_attempt(integ)
        ctx = last_setup_context(integ)
        assert ctx == {"last_error": "", "last_at": "", "last_fields": {}}


@pytest.mark.django_db(transaction=True)
def test_record_setup_attempt_does_not_overwrite_other_meta() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="trello").delete()
        integ = Integration.objects.create(
            provider="trello", is_active=True, meta={"important": "keep me"}
        )
        record_setup_attempt(integ, fields={}, error="boom")
        integ.refresh_from_db()
        assert integ.meta["important"] == "keep me"
        assert integ.meta["last_setup"]["error"] == "boom"
