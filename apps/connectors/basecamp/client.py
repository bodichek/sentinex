from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.basecamp import oauth
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
TIMEOUT = 25.0


class BasecampClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        cred = Credential.objects.filter(integration=integration).first()
        if cred is None:
            raise ValueError("Basecamp integration has no credential")
        self._credential = cred
        self._tokens = cred.get_tokens()
        account_id = self._tokens.get("account_id")
        if not account_id:
            raise ValueError("Basecamp credential missing account_id")
        self._client = http_client or httpx.Client(
            base_url=f"https://3.basecampapi.com/{account_id}",
            timeout=TIMEOUT,
            headers={"User-Agent": "Sentinex (info@sentinex.local)"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BasecampClient:
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

    def list_projects(self) -> list[dict[str, Any]]:
        return list(self._get("/projects.json") or [])

    def list_todolists(self, bucket_id: int) -> list[dict[str, Any]]:
        # Find todoset dock entry, then list its lists.
        project = self._get(f"/projects/{bucket_id}.json")
        todoset = next(
            (
                d
                for d in (project.get("dock") or [])
                if d.get("name") == "todoset" and d.get("enabled")
            ),
            None,
        )
        if not todoset:
            return []
        url = todoset.get("url") or ""
        # url is absolute; reuse path component
        path = url.replace("https://3.basecampapi.com", "").replace(
            f"/{bucket_id}/", f"/{bucket_id}/"
        )
        todoset_obj = self._get(path) if path else {}
        lists_url = todoset_obj.get("todolists_url") or ""
        path = lists_url.replace("https://3.basecampapi.com", "")
        return list(self._get(path)) if path else []

    def list_messages(self, bucket_id: int) -> list[dict[str, Any]]:
        project = self._get(f"/projects/{bucket_id}.json")
        board = next(
            (
                d
                for d in (project.get("dock") or [])
                if d.get("name") == "message_board" and d.get("enabled")
            ),
            None,
        )
        if not board:
            return []
        url = (board.get("url") or "").replace("https://3.basecampapi.com", "")
        if not url:
            return []
        board_obj = self._get(url)
        messages_url = (board_obj.get("messages_url") or "").replace(
            "https://3.basecampapi.com", ""
        )
        return list(self._get(messages_url) or []) if messages_url else []
