"""Per-request Langfuse trace propagation (opt-in)."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.observability.langfuse_client import get_client

logger = logging.getLogger("sentinex.observability.middleware")

ENABLE_HEADER = "X-Sentinex-Trace"


class LangfuseRequestMiddleware:
    """Attach a Langfuse trace to requests that opt in via header.

    Endpoints that want a trace should set the request header
    ``X-Sentinex-Trace: 1`` (the frontend can forward it for diagnostic
    sessions) — keeps the global request volume out of Langfuse by default.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        trace = None
        if request.headers.get(ENABLE_HEADER):
            tenant = getattr(request, "tenant", None)
            tenant_id = str(getattr(tenant, "pk", None) or getattr(tenant, "schema_name", "public"))
            try:
                trace = get_client().trace(
                    tenant_id,
                    name=f"{request.method} {request.path}",
                    input={"path": request.path, "query": request.GET.dict()},
                )
            except Exception:
                logger.exception("failed to create Langfuse request trace")
            if trace is not None and hasattr(trace, "id"):
                request.langfuse_trace_id = trace.id  # type: ignore[attr-defined]

        response = self.get_response(request)
        if trace is not None and hasattr(trace, "update"):
            with contextlib.suppress(Exception):
                trace.update(output={"status_code": response.status_code})
            response.headers[ENABLE_HEADER] = getattr(trace, "id", "")
        return response
