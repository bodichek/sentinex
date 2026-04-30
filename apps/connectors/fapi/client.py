"""FAPI invoicing API client.

Auth: HTTP Basic ``user@email.cz:api_key``.
Docs: https://web.fapi.cz/api-doc/  +  https://fapi.docs.apiary.io/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20.0


def _credentials(integration: Integration) -> tuple[str, str]:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("FAPI integration has no credential")
    tokens = cred.get_tokens()
    user = tokens.get("user")
    api_key = tokens.get("api_key")
    if not (user and api_key):
        raise ValueError("FAPI credential missing user/api_key")
    return str(user), str(api_key)


class FapiClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        user, api_key = _credentials(integration)
        self._client = http_client or httpx.Client(
            base_url="https://api.fapi.cz",
            auth=(user, api_key),
            timeout=DEFAULT_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FapiClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> Any:
        return self._get("/invoices", {"limit": 1})

    def list_invoices(self, limit: int = 100, offset: int = 0) -> Any:
        return self._get("/invoices", {"limit": limit, "offset": offset})

    def list_items(self, limit: int = 100, offset: int = 0) -> Any:
        return self._get("/items", {"limit": limit, "offset": offset})

    def list_clients(self, limit: int = 100, offset: int = 0) -> Any:
        return self._get("/clients", {"limit": limit, "offset": offset})

    def list_vouchers(self, limit: int = 100, offset: int = 0) -> Any:
        return self._get("/vouchers", {"limit": limit, "offset": offset})
