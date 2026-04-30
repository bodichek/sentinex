"""SmartEmailing API v3 client — Basic Auth, JSON, pagination helpers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)

BASE_URL = "https://app.smartemailing.cz/api/v3"
DEFAULT_TIMEOUT = 20.0
DEFAULT_PAGE_LIMIT = 500


def _basic_auth(integration: Integration) -> tuple[str, str]:
    credential = Credential.objects.filter(integration=integration).first()
    if credential is None:
        raise ValueError("SmartEmailing integration has no credential")
    tokens = credential.get_tokens()
    username = tokens.get("username")
    api_key = tokens.get("api_key")
    if not username or not api_key:
        raise ValueError("SmartEmailing credential missing username/api_key")
    return str(username), str(api_key)


class SmartEmailingClient:
    """Read-only HTTP client. Each method returns parsed JSON."""

    def __init__(
        self,
        integration: Integration,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        username, api_key = _basic_auth(integration)
        self._client = http_client or httpx.Client(
            base_url=BASE_URL,
            auth=(username, api_key),
            timeout=DEFAULT_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SmartEmailingClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # -- core ---------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    # -- endpoints ----------------------------------------------------------

    def ping(self) -> dict[str, Any]:
        return self._get("/ping")

    def list_contactlists(self) -> list[dict[str, Any]]:
        data = self._get("/contactlists")
        return list(data.get("data") or [])

    def count_contacts(self, contactlist_id: int | None = None) -> int:
        params: dict[str, Any] = {"limit": 1, "offset": 0}
        if contactlist_id is not None:
            params["contactlist_id"] = contactlist_id
        data = self._get("/contacts", params)
        meta = data.get("meta") or {}
        return int(meta.get("total_count") or len(data.get("data") or []))

    def iter_campaigns(self, page_size: int = DEFAULT_PAGE_LIMIT) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self._get("/campaigns", {"limit": page_size, "offset": offset})
            chunk = data.get("data") or []
            out.extend(chunk)
            if len(chunk) < page_size:
                break
            offset += page_size
        return out

    def campaign_stats(self, campaign_id: int) -> dict[str, Any]:
        data = self._get(f"/campaigns/{campaign_id}/recipients-statistics")
        return dict(data.get("data") or data)
