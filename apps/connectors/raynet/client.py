"""Raynet CRM REST API client.

Auth: HTTP Basic with username + API key. Each tenant configures its own
``instance`` (subdomain — e.g. ``acme`` for ``app.raynet.cz/acme``).
Docs: https://app.raynetcrm.com/api/doc/index-en.html
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20.0


def _credentials(integration: Integration) -> tuple[str, str, str]:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Raynet integration has no credential")
    tokens = cred.get_tokens()
    instance = tokens.get("instance")
    username = tokens.get("username")
    api_key = tokens.get("api_key")
    if not (instance and username and api_key):
        raise ValueError("Raynet credential missing instance/username/api_key")
    return str(instance), str(username), str(api_key)


class RaynetClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        instance, username, api_key = _credentials(integration)
        self._instance = instance
        self._client = http_client or httpx.Client(
            base_url=f"https://app.raynet.cz/{instance}/api/v2",
            auth=(username, api_key),
            timeout=DEFAULT_TIMEOUT,
            headers={"Accept": "application/json", "X-Instance-Name": instance},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RaynetClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> dict[str, Any]:
        return dict(self._get("/company/", {"limit": 1, "offset": 0}))

    def list_companies(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return dict(self._get("/company/", {"limit": limit, "offset": offset}))

    def list_leads(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return dict(self._get("/lead/", {"limit": limit, "offset": offset}))

    def list_business_cases(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return dict(self._get("/businessCase/", {"limit": limit, "offset": offset}))

    def list_offers(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return dict(self._get("/offer/", {"limit": limit, "offset": offset}))

    def list_invoices(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return dict(self._get("/invoice/", {"limit": limit, "offset": offset}))
