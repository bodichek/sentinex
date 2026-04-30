from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.hubspot import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
BASE = "https://api.hubapi.com"
TIMEOUT = 30.0


class HubspotClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("HubSpot integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        self._client = http_client or httpx.Client(base_url=BASE, timeout=TIMEOUT)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HubspotClient:
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

    def list_contacts(self, limit: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        params: dict[str, Any] = {"limit": limit}
        while True:
            data = self._get("/crm/v3/objects/contacts", params)
            out.extend(data.get("results") or [])
            paging = (data.get("paging") or {}).get("next") or {}
            after = paging.get("after")
            if not after or len(out) >= 1000:
                break
            params = {"limit": limit, "after": after}
        return out

    def list_deals(self, limit: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        params: dict[str, Any] = {
            "limit": limit,
            "properties": "dealname,amount,dealstage,pipeline,closedate,hs_is_closed_won,hs_is_closed",
        }
        while True:
            data = self._get("/crm/v3/objects/deals", params)
            out.extend(data.get("results") or [])
            paging = (data.get("paging") or {}).get("next") or {}
            after = paging.get("after")
            if not after or len(out) >= 2000:
                break
            params["after"] = after
        return out

    def list_pipelines(self) -> list[dict[str, Any]]:
        return list(self._get("/crm/v3/pipelines/deals").get("results") or [])

    def list_companies(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._get("/crm/v3/objects/companies", {"limit": limit}).get("results") or [])

    def list_tickets(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._get("/crm/v3/objects/tickets", {"limit": limit}).get("results") or [])
