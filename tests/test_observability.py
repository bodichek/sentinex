"""Observability + auth-hash tests."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import override_settings

from apps.agents.llm_gateway import LLMResponse, complete
from apps.core.models import User


def test_sentry_skips_without_dsn() -> None:
    """Importing settings with SENTRY_DSN unset must not raise."""
    assert settings.SENTRY_DSN == ""


@pytest.mark.django_db(transaction=True)
@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.Argon2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
)
def test_argon2_hashes_password() -> None:
    from config.settings import base as base_settings

    assert base_settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    user = User.objects.create_user(email="argon@example.com", password="pw-12345678")
    assert user.password.startswith("argon2")


def test_llm_log_emitted(caplog: pytest.LogCaptureFixture) -> None:
    fake = type(
        "Msg",
        (),
        {
            "content": [type("B", (), {"type": "text", "text": "hi"})()],
            "usage": type("U", (), {"input_tokens": 10, "output_tokens": 5})(),
            "stop_reason": "end_turn",
        },
    )()

    with (
        patch("apps.agents.llm_gateway._call_anthropic", return_value=fake),
        patch(
            "apps.agents.llm_gateway.compute_cost_czk", return_value=Decimal("0.24")
        ),
        patch("apps.agents.llm_gateway._record_usage"),
        patch("apps.agents.llm_gateway.cache") as mock_cache,
    ):
        mock_cache.get.return_value = None
        with caplog.at_level(logging.INFO, logger="sentinex.llm"):
            response = complete("test prompt", cache_ttl=0)

    assert isinstance(response, LLMResponse)
    llm_records = [r for r in caplog.records if r.name == "sentinex.llm"]
    assert llm_records, "expected a sentinex.llm log record"
    payload = json.loads(llm_records[-1].message)
    assert payload["event"] == "llm_call"
    assert payload["tokens"] == 15
    assert "cost_usd" in payload
    assert "latency_ms" in payload
