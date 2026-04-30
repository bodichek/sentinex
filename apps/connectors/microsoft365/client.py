"""Microsoft Graph REST client. Auto-refresh on 401."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.microsoft365 import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DEFAULT_TIMEOUT = 30.0


def _credential(integration: Integration) -> Credential:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Microsoft 365 integration has no credential")
    return cred


class Microsoft365Client:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        self._integration = integration
        self._credential = _credential(integration)
        self._tokens = self._credential.get_tokens()
        self._client = http_client or httpx.Client(
            base_url=GRAPH_BASE, timeout=DEFAULT_TIMEOUT
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Microsoft365Client:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens.get('access_token','')}",
            "Accept": "application/json",
        }

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
        return dict(self._get("/me"))

    def list_messages(self, top: int = 50) -> list[dict[str, Any]]:
        return list(
            (self._get("/me/messages", {"$top": top, "$select": "subject,from,receivedDateTime,isRead"})).get(
                "value", []
            )
        )

    def list_calendar_events(self, days: int = 14) -> list[dict[str, Any]]:
        from datetime import timedelta

        from django.utils import timezone as dj_tz

        start = dj_tz.now().isoformat()
        end = (dj_tz.now() + timedelta(days=days)).isoformat()
        return list(
            self._get(
                "/me/calendar/calendarView",
                {"startDateTime": start, "endDateTime": end, "$top": 100},
            ).get("value", [])
        )

    def list_drive_root(self, top: int = 100) -> list[dict[str, Any]]:
        return list(
            (self._get("/me/drive/root/children", {"$top": top})).get("value", [])
        )

    def list_joined_teams(self) -> list[dict[str, Any]]:
        return list((self._get("/me/joinedTeams")).get("value", []))

    def list_channels(self, team_id: str) -> list[dict[str, Any]]:
        return list((self._get(f"/teams/{team_id}/channels")).get("value", []))
