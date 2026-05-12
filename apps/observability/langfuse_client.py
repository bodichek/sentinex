"""Langfuse client wrapper.

Tenant isolation = Option A (tags). The wrapper exposes:

* :meth:`get_callback_handler` — for LangGraph (LangChain CallbackHandler).
* :meth:`trace` — for direct SDK usage outside of LangGraph.

When ``LANGFUSE_ENABLED`` is false (default in tests), all methods return
``None`` so that calling code stays a no-op without requiring conditionals.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from langfuse import Langfuse
    from langfuse.callback import CallbackHandler

logger = logging.getLogger("sentinex.observability")


class SentinexLangfuseClient:
    """Tenant-aware façade over the Langfuse SDK."""

    def __init__(self, langfuse: Langfuse | None = None) -> None:
        self._langfuse = langfuse

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "LANGFUSE_ENABLED", False))

    def _sample(self) -> bool:
        rate = float(getattr(settings, "LANGFUSE_SAMPLE_RATE", 1.0))
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        return random.random() < rate

    def _get_sdk(self) -> Langfuse | None:
        if not self.enabled:
            return None
        if self._langfuse is None:
            try:
                from langfuse import Langfuse
            except ImportError:
                return None
            self._langfuse = Langfuse(
                public_key=getattr(settings, "LANGFUSE_PUBLIC_KEY", None),
                secret_key=getattr(settings, "LANGFUSE_SECRET_KEY", None),
                host=getattr(settings, "LANGFUSE_HOST", None),
            )
        return self._langfuse

    def get_callback_handler(
        self,
        tenant_id: str,
        agent_type: str,
        run_id: str | None = None,
    ) -> CallbackHandler | None:
        """Return a LangChain CallbackHandler with per-tenant tags."""
        if not self.enabled or not self._sample():
            return None
        try:
            from langfuse.callback import CallbackHandler
        except ImportError:
            return None
        tags = [
            f"tenant:{tenant_id}",
            f"agent:{agent_type}",
            f"env:{getattr(settings, 'SENTRY_ENVIRONMENT', 'development')}",
        ]
        if run_id:
            tags.append(f"run:{run_id}")
        return CallbackHandler(
            public_key=getattr(settings, "LANGFUSE_PUBLIC_KEY", None),
            secret_key=getattr(settings, "LANGFUSE_SECRET_KEY", None),
            host=getattr(settings, "LANGFUSE_HOST", None),
            tags=tags,
        )

    def trace(
        self,
        tenant_id: str,
        name: str,
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create (and return) a Langfuse trace; ``None`` when disabled."""
        sdk = self._get_sdk()
        if sdk is None:
            return None
        meta = {"tenant_id": tenant_id, **(metadata or {})}
        return sdk.trace(name=name, input=input, output=output, metadata=meta, tags=[f"tenant:{tenant_id}"])

    def trace_url(self, trace_id: str) -> str | None:
        host = getattr(settings, "LANGFUSE_HOST", None)
        if not host or not trace_id:
            return None
        return f"{host.rstrip('/')}/trace/{trace_id}"


_default_client: SentinexLangfuseClient | None = None


def get_client() -> SentinexLangfuseClient:
    global _default_client
    if _default_client is None:
        _default_client = SentinexLangfuseClient()
    return _default_client
