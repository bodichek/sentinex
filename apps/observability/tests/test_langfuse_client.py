"""Tests for the SentinexLangfuseClient wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import override_settings

from apps.observability.langfuse_client import SentinexLangfuseClient


@override_settings(LANGFUSE_ENABLED=False)
def test_callback_handler_returns_none_when_disabled() -> None:
    client = SentinexLangfuseClient()
    assert client.get_callback_handler("t1", "research") is None


@override_settings(LANGFUSE_ENABLED=True, LANGFUSE_SAMPLE_RATE=0.0)
def test_callback_handler_respects_zero_sample_rate() -> None:
    client = SentinexLangfuseClient()
    assert client.get_callback_handler("t1", "research") is None


@override_settings(LANGFUSE_ENABLED=True, LANGFUSE_SAMPLE_RATE=1.0)
def test_callback_handler_includes_tenant_and_agent_tags() -> None:
    fake_handler = MagicMock()
    with patch("langfuse.callback.CallbackHandler", return_value=fake_handler) as patched:
        client = SentinexLangfuseClient()
        result = client.get_callback_handler("acme", "research", run_id="r1")
    assert result is fake_handler
    kwargs = patched.call_args.kwargs
    tags = kwargs["tags"]
    assert "tenant:acme" in tags
    assert "agent:research" in tags
    assert "run:r1" in tags


@override_settings(LANGFUSE_ENABLED=False)
def test_trace_returns_none_when_disabled() -> None:
    client = SentinexLangfuseClient()
    assert client.trace("t1", "name") is None


@override_settings(LANGFUSE_ENABLED=True, LANGFUSE_HOST="http://lf.local")
def test_trace_url_uses_configured_host() -> None:
    client = SentinexLangfuseClient(langfuse=MagicMock())
    assert client.trace_url("abc") == "http://lf.local/trace/abc"
