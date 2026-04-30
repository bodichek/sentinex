"""Salesforce REST client. Per-org instance URL stored in Credential."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.salesforce import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
API_VERSION = "v60.0"
DEFAULT_TIMEOUT = 30.0


class SalesforceClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("Salesforce integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        instance = self._tokens.get("instance_url") or "https://login.salesforce.com"
        self._client = http_client or httpx.Client(
            base_url=f"{instance}/services/data/{API_VERSION}", timeout=DEFAULT_TIMEOUT
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SalesforceClient:
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

    def query(self, soql: str) -> dict[str, Any]:
        return dict(self._get("/query", {"q": soql}))

    def list_accounts(self, limit: int = 200) -> dict[str, Any]:
        return self.query(
            f"SELECT Id, Name, Industry, AnnualRevenue, NumberOfEmployees, "
            f"OwnerId, CreatedDate FROM Account ORDER BY CreatedDate DESC LIMIT {int(limit)}"
        )

    def list_opportunities(self, limit: int = 500) -> dict[str, Any]:
        return self.query(
            f"SELECT Id, Name, StageName, Amount, CloseDate, IsClosed, IsWon, OwnerId "
            f"FROM Opportunity ORDER BY CloseDate DESC LIMIT {int(limit)}"
        )

    def list_leads(self, limit: int = 200) -> dict[str, Any]:
        return self.query(
            f"SELECT Id, Status, Company, Industry, CreatedDate FROM Lead "
            f"ORDER BY CreatedDate DESC LIMIT {int(limit)}"
        )

    def list_users(self, limit: int = 200) -> dict[str, Any]:
        return self.query(
            f"SELECT Id, Name, Email, IsActive FROM User WHERE IsActive = true LIMIT {int(limit)}"
        )
