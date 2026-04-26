"""Unit tests for apps.agents.llm_gateway.

Anthropic client is mocked for all unit tests. Integration test marked
``@pytest.mark.integration`` makes a real API call.
"""

from __future__ import annotations

import os
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIConnectionError, AuthenticationError, RateLimitError
from django.core.cache import cache

from apps.agents import llm_gateway
from apps.agents.llm_gateway import (
    LLMAuthError,
    LLMRateLimitError,
    LLMUnavailableError,
    complete,
)
from apps.agents.pricing import compute_cost_czk, resolve_model
from apps.core.models import LLMUsage, Tenant


def _fake_message(text: str = "hi", input_tokens: int = 10, output_tokens: int = 5) -> Any:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason="end_turn",
    )


@pytest.fixture(autouse=True)
def _reset_client_and_cache() -> None:
    llm_gateway._client = None
    cache.clear()


@pytest.mark.django_db
class TestPricing:
    def test_resolve_alias(self) -> None:
        assert resolve_model("sonnet") == "claude-sonnet-4-20250514"
        assert resolve_model("haiku") == "claude-haiku-4-5-20251001"
        assert resolve_model("claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"

    def test_cost_computation(self) -> None:
        cost = compute_cost_czk("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
        # 1 USD in + 5 USD out = 6 USD * 24 CZK
        assert cost == Decimal("144.0000")


@pytest.mark.django_db
class TestGatewayCache:
    def test_cache_miss_then_hit(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = "test-key"
        with patch.object(llm_gateway, "_call_anthropic", return_value=_fake_message("hello")) as mock_call:
            r1 = complete("ping", model="haiku")
            r2 = complete("ping", model="haiku")

        assert r1.cached is False
        assert r2.cached is True
        assert r2.content == "hello"
        assert mock_call.call_count == 1

    def test_records_usage_for_both_hits(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = "test-key"
        tenant = Tenant.objects.create(schema_name="usage_t", name="UT")
        with patch.object(llm_gateway, "_call_anthropic", return_value=_fake_message()):
            complete("x", model="haiku", tenant=tenant)
            complete("x", model="haiku", tenant=tenant)
        rows = list(LLMUsage.objects.filter(tenant=tenant).order_by("created_at"))
        assert len(rows) == 2
        assert rows[0].cached is False
        assert rows[1].cached is True


@pytest.mark.django_db
class TestErrorMapping:
    def test_auth_error(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = "test-key"
        err = AuthenticationError(
            message="bad", response=MagicMock(status_code=401), body=None
        )
        with (
            patch.object(llm_gateway, "_call_anthropic", side_effect=err),
            pytest.raises(LLMAuthError),
        ):
            complete("x", model="haiku", cache_ttl=0)

    def test_rate_limit_error(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = "test-key"
        err = RateLimitError(message="slow", response=MagicMock(status_code=429), body=None)
        with (
            patch.object(llm_gateway, "_call_anthropic", side_effect=err),
            pytest.raises(LLMRateLimitError),
        ):
            complete("x", model="haiku", cache_ttl=0)

    def test_connection_error(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = "test-key"
        err = APIConnectionError(request=MagicMock())
        with (
            patch.object(llm_gateway, "_call_anthropic", side_effect=err),
            pytest.raises(LLMUnavailableError),
        ):
            complete("x", model="haiku", cache_ttl=0)

    def test_missing_api_key(self, settings: Any) -> None:
        settings.ANTHROPIC_API_KEY = ""
        with pytest.raises(LLMAuthError):
            complete("x", model="haiku", cache_ttl=0)


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No ANTHROPIC_API_KEY set; skipping real API integration test.",
)
class TestIntegration:
    def test_real_call_returns_content(self) -> None:
        response = complete("Reply with exactly: OK", model="haiku", cache_ttl=0, max_tokens=16)
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0
