from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.asana import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
BASE = "https://app.asana.com/api/1.0"
TIMEOUT = 25.0


class AsanaClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("Asana integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        self._client = http_client or httpx.Client(base_url=BASE, timeout=TIMEOUT)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AsanaClient:
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
        return dict((self._get("/users/me")).get("data") or {})

    def list_workspaces(self) -> list[dict[str, Any]]:
        return list((self._get("/workspaces")).get("data") or [])

    def list_projects(self, workspace_gid: str, limit: int = 100) -> list[dict[str, Any]]:
        return list(
            (
                self._get(
                    "/projects",
                    {"workspace": workspace_gid, "archived": "false", "limit": limit},
                )
            ).get("data")
            or []
        )

    def list_tasks(self, project_gid: str, limit: int = 100) -> list[dict[str, Any]]:
        return list(
            (
                self._get(
                    f"/projects/{project_gid}/tasks",
                    {"limit": limit, "opt_fields": "name,completed,due_on,assignee.name,modified_at"},
                )
            ).get("data")
            or []
        )
