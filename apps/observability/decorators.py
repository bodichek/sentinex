"""Decorator for manual Langfuse tracing of arbitrary functions."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from apps.observability.langfuse_client import get_client

F = TypeVar("F", bound=Callable[..., Any])


def _tenant_from_request(request: Any) -> str:
    tenant = getattr(getattr(request, "_request", request), "tenant", None) or getattr(
        request, "tenant", None
    )
    return str(getattr(tenant, "pk", None) or getattr(tenant, "schema_name", "public"))


def langfuse_trace(name: str | None = None, tenant_from: str = "request") -> Callable[[F], F]:
    """Wrap a function in a Langfuse trace.

    ``tenant_from`` selects the source of the tenant id:
    * ``"request"`` — first arg is a Django/DRF ``request`` object.
    * any other string — looked up as a kwarg name.
    """

    def decorate(fn: F) -> F:
        trace_name = name or fn.__name__
        is_async = inspect.iscoroutinefunction(fn)

        if is_async:
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                client = get_client()
                tenant = _resolve_tenant(args, kwargs, tenant_from)
                trace = client.trace(tenant, trace_name, input={"args": _safe(args), "kwargs": _safe(kwargs)})
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    if trace is not None and hasattr(trace, "update"):
                        trace.update(status_message=str(exc), level="ERROR")
                    raise
                if trace is not None and hasattr(trace, "update"):
                    trace.update(output={"result": _safe(result)})
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_client()
            tenant = _resolve_tenant(args, kwargs, tenant_from)
            trace = client.trace(tenant, trace_name, input={"args": _safe(args), "kwargs": _safe(kwargs)})
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                if trace is not None and hasattr(trace, "update"):
                    trace.update(status_message=str(exc), level="ERROR")
                raise
            if trace is not None and hasattr(trace, "update"):
                trace.update(output={"result": _safe(result)})
            return result

        return sync_wrapper  # type: ignore[return-value]

    return decorate


def _resolve_tenant(args: tuple[Any, ...], kwargs: dict[str, Any], source: str) -> str:
    if source == "request":
        if args:
            return _tenant_from_request(args[0])
        return "public"
    return str(kwargs.get(source, "public"))


def _safe(value: Any) -> Any:
    try:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return {str(k): _safe(v) for k, v in value.items() if not str(k).startswith("_")}
        if isinstance(value, (list, tuple)):
            return [_safe(v) for v in value][:10]
        return repr(value)[:200]
    except Exception:  # noqa: BLE001
        return "<unserialisable>"


# wrap as Awaitable type hint to silence mypy on call sites
AsyncFn = Callable[..., Awaitable[Any]]
