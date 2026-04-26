"""Print health check status from the CLI."""

from __future__ import annotations

import json
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verify DB + cache connectivity. Exits non-zero on failure."

    def handle(self, *args: Any, **opts: Any) -> None:
        report: dict[str, Any] = {"database": "unknown", "cache": "unknown"}
        ok = True

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            report["database"] = "ok"
        except Exception as exc:
            report["database"] = f"error: {exc}"
            ok = False

        try:
            cache.set("_health_cli", "ok", 5)
            report["cache"] = "ok" if cache.get("_health_cli") == "ok" else "miss"
        except Exception as exc:
            report["cache"] = f"error: {exc}"
            ok = False

        self.stdout.write(json.dumps(report, indent=2))
        if not ok:
            raise SystemExit(1)
