"""Health check view: verifies DB + Redis reachable."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse


def healthcheck(request: HttpRequest) -> JsonResponse:
    status: dict[str, Any] = {"status": "ok"}

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        status["database"] = "ok"
    except Exception as exc:
        status["status"] = "degraded"
        status["database"] = f"error: {exc}"

    try:
        cache.set("_health", "ok", 10)
        assert cache.get("_health") == "ok"
        status["cache"] = "ok"
    except Exception as exc:
        status["status"] = "degraded"
        status["cache"] = f"error: {exc}"

    http_status = 200 if status["status"] == "ok" else 503
    return JsonResponse(status, status=http_status)
