"""Caflou REST API v1 client.

Auth: Bearer token (per-tenant, generated in Caflou Settings → API).
Docs: https://docs.caflou.cz/integrace/api  +
      https://documenter.getpostman.com/view/4786951/RWMFrTQC
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20.0


def _bearer(integration: Integration) -> str:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Caflou integration has no credential")
    token = (cred.get_tokens() or {}).get("api_token")
    if not token:
        raise ValueError("Caflou credential missing api_token")
    return str(token)


class CaflouClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        token = _bearer(integration)
        self._client = http_client or httpx.Client(
            base_url="https://app.caflou.com/api/v1",
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CaflouClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> dict[str, Any]:
        return dict(self._get("/users/me"))

    def list_companies(self, page: int = 1, per_page: int = 100) -> Any:
        return self._get("/companies", {"page": page, "per_page": per_page})

    def list_projects(self, page: int = 1, per_page: int = 100) -> Any:
        return self._get("/projects", {"page": page, "per_page": per_page})

    def list_tasks(self, page: int = 1, per_page: int = 100) -> Any:
        return self._get("/tasks", {"page": page, "per_page": per_page})

    def list_invoices(self, page: int = 1, per_page: int = 100) -> Any:
        return self._get("/invoices", {"page": page, "per_page": per_page})

    def list_timesheets(self, page: int = 1, per_page: int = 100) -> Any:
        return self._get("/timesheets", {"page": page, "per_page": per_page})
