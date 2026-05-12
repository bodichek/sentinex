"""Tests for the langfuse_trace decorator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from apps.observability.decorators import langfuse_trace


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def test_decorator_passes_through_when_langfuse_disabled() -> None:
    with patch("apps.observability.decorators.get_client") as gc:
        client = MagicMock()
        client.trace.return_value = None
        gc.return_value = client

        @langfuse_trace(name="adder", tenant_from="tenant_id")
        def add(a: int, b: int, tenant_id: str = "t1") -> int:
            return a + b

        assert add(2, 3) == 5


def test_decorator_updates_trace_with_output_on_success() -> None:
    trace = MagicMock()
    with patch("apps.observability.decorators.get_client") as gc:
        client = MagicMock()
        client.trace.return_value = trace
        gc.return_value = client

        @langfuse_trace(name="adder", tenant_from="tenant_id")
        def add(a: int, b: int, tenant_id: str = "t1") -> int:
            return a + b

        add(2, 3, tenant_id="acme")

    trace.update.assert_called()
    last_kwargs = trace.update.call_args.kwargs
    assert last_kwargs["output"] == {"result": 5}


def test_decorator_records_error_level_on_exception() -> None:
    trace = MagicMock()
    with patch("apps.observability.decorators.get_client") as gc:
        client = MagicMock()
        client.trace.return_value = trace
        gc.return_value = client

        @langfuse_trace(name="boom", tenant_from="tenant_id")
        async def boom(tenant_id: str = "t1") -> int:
            raise ValueError("nope")

        try:
            _run(boom(tenant_id="acme"))
        except ValueError:
            pass

    trace.update.assert_called()
    kwargs = trace.update.call_args.kwargs
    assert kwargs["level"] == "ERROR"
