from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
TIMEOUT = 25.0


def _credentials(integration: Integration) -> tuple[str, str]:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Mailchimp integration has no credential")
    tokens = cred.get_tokens()
    api_endpoint = tokens.get("api_endpoint") or (
        f"https://{tokens.get('dc')}.api.mailchimp.com" if tokens.get("dc") else ""
    )
    if not api_endpoint or not tokens.get("access_token"):
        raise ValueError("Mailchimp credential missing api_endpoint/access_token")
    return str(api_endpoint), str(tokens["access_token"])


class MailchimpClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        api_endpoint, access_token = _credentials(integration)
        self._client = http_client or httpx.Client(
            base_url=f"{api_endpoint}/3.0",
            timeout=TIMEOUT,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MailchimpClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> Any:
        return self._get("/ping")

    def list_audiences(self, count: int = 100) -> list[dict[str, Any]]:
        return list((self._get("/lists", {"count": count})).get("lists") or [])

    def list_campaigns(self, count: int = 100) -> list[dict[str, Any]]:
        return list((self._get("/campaigns", {"count": count})).get("campaigns") or [])

    def campaign_report(self, campaign_id: str) -> dict[str, Any]:
        return dict(self._get(f"/reports/{campaign_id}"))
