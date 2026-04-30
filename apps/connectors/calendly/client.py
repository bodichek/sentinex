from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.calendly import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
BASE = "https://api.calendly.com"
TIMEOUT = 25.0


class CalendlyClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("Calendly integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        self._client = http_client or httpx.Client(base_url=BASE, timeout=TIMEOUT)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CalendlyClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.get('access_token','')}"}

    def _refresh(self) -> None:
        new = oauth.refresh_tokens(self._tokens)
        merged = {**self._tokens, **new}
        self._tokens = merged
        self._credential.set_tokens(merged)
        self._credential.save()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, headers=self._headers(), params=params)
        if resp.status_code == 401:
            self._refresh()
            resp = self._client.get(path, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def me(self) -> dict[str, Any]:
        return dict((self._get("/users/me")).get("resource") or {})

    def list_event_types(self) -> list[dict[str, Any]]:
        owner = self._tokens.get("owner")
        if not owner:
            owner = self.me().get("uri")
        return list(
            (self._get("/event_types", {"user": owner, "count": 100})).get("collection") or []
        )

    def list_scheduled_events(
        self, days_back: int = 30, count: int = 100
    ) -> list[dict[str, Any]]:
        from datetime import timedelta

        from django.utils import timezone as dj_tz

        owner = self._tokens.get("owner")
        if not owner:
            owner = self.me().get("uri")
        min_start = (dj_tz.now() - timedelta(days=days_back)).isoformat()
        return list(
            (
                self._get(
                    "/scheduled_events",
                    {"user": owner, "min_start_time": min_start, "count": count},
                )
            ).get("collection")
            or []
        )

    def list_invitees(self, event_uri: str) -> list[dict[str, Any]]:
        # event_uri ends with the UUID; the path uses the UUID directly
        if "/scheduled_events/" not in event_uri:
            return []
        uid = event_uri.rsplit("/", 1)[-1]
        return list(
            (self._get(f"/scheduled_events/{uid}/invitees", {"count": 100})).get("collection") or []
        )
