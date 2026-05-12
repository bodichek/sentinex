"""Tests for the prompt manager (Langfuse + Redis cache + local fallback)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.observability import prompt_manager


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def test_get_prompt_returns_cached_value_without_calling_langfuse() -> None:
    with patch.object(prompt_manager, "cache") as cache_mock:
        cache_mock.get.return_value = "cached body"
        out = _run(prompt_manager.get_prompt("welcome"))
    assert out == "cached body"


def test_get_prompt_falls_back_to_local_file_when_langfuse_disabled(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "research.md"
    target.write_text("local body", encoding="utf-8")
    with patch.object(prompt_manager, "cache") as cache_mock, \
         patch.object(prompt_manager, "LOCAL_PROMPTS_DIR", tmp_path), \
         patch.object(prompt_manager, "get_client") as get_client_mock:
        cache_mock.get.return_value = None
        client_mock = MagicMock()
        client_mock._get_sdk.return_value = None
        get_client_mock.return_value = client_mock
        out = _run(prompt_manager.get_prompt("research"))
    assert out == "local body"


def test_get_prompt_raises_when_neither_langfuse_nor_local() -> None:
    with patch.object(prompt_manager, "cache") as cache_mock, \
         patch.object(prompt_manager, "get_client") as get_client_mock:
        cache_mock.get.return_value = None
        client_mock = MagicMock()
        client_mock._get_sdk.return_value = None
        get_client_mock.return_value = client_mock
        with pytest.raises(FileNotFoundError):
            _run(prompt_manager.get_prompt("does-not-exist-anywhere-xyz"))


def test_get_prompt_uses_langfuse_then_caches_result(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fake_prompt = MagicMock()
    fake_prompt.prompt = "from langfuse"
    sdk = MagicMock()
    sdk.get_prompt.return_value = fake_prompt
    with patch.object(prompt_manager, "cache") as cache_mock, \
         patch.object(prompt_manager, "get_client") as get_client_mock:
        cache_mock.get.return_value = None
        client_mock = MagicMock()
        client_mock._get_sdk.return_value = sdk
        get_client_mock.return_value = client_mock
        out = _run(prompt_manager.get_prompt("hello"))
    assert out == "from langfuse"
    cache_mock.set.assert_called_once()
