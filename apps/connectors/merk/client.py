"""Merk.cz HTTP client.

Merk uses an API key in the Authorization header (exact format to confirm
when the SCB API key is available — see docs/connectors/merk.md).
The client is intentionally thin so the precise auth header can be adjusted
without touching ingest code.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from apps.connectors._framework.retry import retry_with_backoff
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.merk.cz/v1"
DEFAULT_TIMEOUT = 20.0


class MerkClientError(RuntimeError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _api_key(integration: Integration) -> str:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise MerkClientError("Merk integration has no credential")
    tokens = cred.get_tokens()
    key = tokens.get("api_key") or ""
    if not key:
        raise MerkClientError("Merk credential missing api_key")
    return key


class MerkClient:
    def __init__(
        self,
        integration: Integration | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if api_key is None and integration is not None:
            api_key = _api_key(integration)
        if api_key is None:
            raise MerkClientError("Merk client needs api_key or integration")
        self._api_key = api_key
        self._client = http_client or httpx.Client(
            base_url=base_url or getattr(settings, "MERK_BASE_URL", DEFAULT_BASE_URL),
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Accept": "application/json",
                "Authorization": f"ApiKey {api_key}",
            },
        )

    def __enter__(self) -> MerkClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self._client.close()

    @retry_with_backoff(retries=3, base_delay=1.0)
    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After") or 0) or None
            raise MerkClientError("rate limited", retry_after=retry_after)
        resp.raise_for_status()
        return resp.json()

    @retry_with_backoff(retries=3, base_delay=1.0)
    def _post(self, path: str, body: dict[str, Any]) -> Any:
        resp = self._client.post(path, json=body)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After") or 0) or None
            raise MerkClientError("rate limited", retry_after=retry_after)
        resp.raise_for_status()
        return resp.json()

    # ----------------------------------------------------------- public API
    def lookup_by_ico(self, ico: str) -> dict[str, Any]:
        """GET /subjects/{ico} — single-company lookup."""
        return self._get(f"/subjects/{ico}")

    def batch_lookup(self, icos: list[str]) -> list[dict[str, Any]]:
        """POST /subjects/batch — up to 500 IČOs per request."""
        if len(icos) > 500:
            raise ValueError("Merk batch supports max 500 IČOs per request")
        resp = self._post("/subjects/batch", {"icos": list(icos)})
        if isinstance(resp, dict):
            return list(resp.get("subjects") or resp.get("data") or [])
        return list(resp)

    def suggest(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """GET /subjects/suggest — autocomplete by name/email."""
        resp = self._get("/subjects/suggest", {"query": query, "limit": limit})
        if isinstance(resp, dict):
            return list(resp.get("suggestions") or resp.get("data") or [])
        return list(resp)

    def financials(self, ico: str) -> dict[str, Any]:
        return self._get(f"/subjects/{ico}/financials")
