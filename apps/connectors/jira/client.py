from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.jira import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
TIMEOUT = 30.0


class JiraClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("Jira integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        cloud_id = self._tokens.get("cloud_id")
        if not cloud_id:
            raise ValueError("Jira credential missing cloud_id")
        self._client = http_client or httpx.Client(
            base_url=f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3",
            timeout=TIMEOUT,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JiraClient:
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

    def myself(self) -> dict[str, Any]:
        return dict(self._get("/myself"))

    def search(self, jql: str, fields: str = "summary,status,priority,assignee,created", max_results: int = 100) -> dict[str, Any]:
        return dict(self._get("/search", {"jql": jql, "fields": fields, "maxResults": max_results}))

    def list_projects(self) -> list[dict[str, Any]]:
        return list(self._get("/project/search", {"maxResults": 100}).get("values") or [])
