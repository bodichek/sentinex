"""Google Workspace via Service Account + Domain-Wide Delegation.

Single connector that impersonates any user in the configured Workspace domain
to read Gmail, Drive, Calendar, Docs, Sheets, Slides, Directory, Reports, etc.

Setup (one-time, by Workspace admin):
    1. Create Service Account in Google Cloud Console.
    2. Download JSON key; point ``GOOGLE_WORKSPACE_SA_JSON_PATH`` at it
       (or paste contents into ``GOOGLE_WORKSPACE_SA_JSON``).
    3. In Workspace Admin Console > Security > API Controls > Domain-Wide
       Delegation: add the SA's Unique ID and authorize all scopes from
       ``settings.GOOGLE_WORKSPACE_DWD_SCOPES``.
    4. Set ``GOOGLE_WORKSPACE_DOMAIN`` and ``GOOGLE_WORKSPACE_ADMIN_EMAIL``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from functools import lru_cache
from typing import Any

from django.conf import settings

from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

_SA_INFO_LOCK = threading.Lock()
_SA_INFO_CACHE: dict[str, Any] | None = None


def _load_sa_info() -> dict[str, Any]:
    """Load service-account JSON dict from settings (file path or inline JSON)."""
    global _SA_INFO_CACHE
    with _SA_INFO_LOCK:
        if _SA_INFO_CACHE is not None:
            return _SA_INFO_CACHE
        path = settings.GOOGLE_WORKSPACE_SA_JSON_PATH
        inline = settings.GOOGLE_WORKSPACE_SA_JSON
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                _SA_INFO_CACHE = json.load(fh)
        elif inline:
            _SA_INFO_CACHE = json.loads(inline)
        else:
            raise RuntimeError(
                "Google Workspace DWD not configured: set "
                "GOOGLE_WORKSPACE_SA_JSON_PATH or GOOGLE_WORKSPACE_SA_JSON."
            )
        return _SA_INFO_CACHE


def reset_sa_cache() -> None:
    """Test hook — clear cached SA info (e.g., after monkeypatching settings)."""
    global _SA_INFO_CACHE
    with _SA_INFO_LOCK:
        _SA_INFO_CACHE = None


def _validate_subject_domain(subject: str) -> None:
    """Reject subjects outside the configured Workspace domain.

    Without this check any caller could impersonate users belonging to a
    different Google Workspace tenant — a cross-tenant escalation.
    """
    domain = (settings.GOOGLE_WORKSPACE_DOMAIN or "").lower().strip()
    if not domain:
        raise RuntimeError(
            "GOOGLE_WORKSPACE_DOMAIN must be configured before delegating credentials."
        )
    parts = subject.lower().rsplit("@", 1)
    if len(parts) != 2 or parts[1] != domain:
        raise RuntimeError(
            f"subject '{subject}' is not in the configured Workspace domain '{domain}'"
        )


def get_credentials(subject: str | None = None, scopes: list[str] | None = None) -> Any:
    """Return delegated google.oauth2.service_account.Credentials for ``subject``.

    ``subject`` defaults to the configured admin email — useful for domain-wide
    queries (Drive ``corpora=domain``, Admin SDK Directory). Use a specific user
    email when fetching that user's Gmail/Calendar.
    """
    from google.oauth2 import service_account  # type: ignore[import-not-found]

    info = _load_sa_info()
    subject = subject or settings.GOOGLE_WORKSPACE_ADMIN_EMAIL
    if not subject:
        raise RuntimeError("subject email required (no GOOGLE_WORKSPACE_ADMIN_EMAIL set)")
    _validate_subject_domain(subject)
    scopes = scopes or list(settings.GOOGLE_WORKSPACE_DWD_SCOPES)
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return creds.with_subject(subject)


@lru_cache(maxsize=64)
def _build_service_cached(api: str, version: str, subject: str, scope_key: str) -> Any:
    from googleapiclient.discovery import build  # type: ignore[import-not-found]

    scopes = list(scope_key.split(",")) if scope_key else None
    creds = get_credentials(subject=subject, scopes=scopes)
    return build(api, version, credentials=creds, cache_discovery=False)


def build_service(
    api: str,
    version: str,
    subject: str | None = None,
    scopes: list[str] | None = None,
) -> Any:
    """Build a googleapiclient service. Cached per (api, version, subject, scopes)."""
    subject = subject or settings.GOOGLE_WORKSPACE_ADMIN_EMAIL
    scope_key = ",".join(sorted(scopes)) if scopes else ""
    return _build_service_cached(api, version, subject, scope_key)


# ---------------------------------------------------------------------------
# Convenience client factories — one line per API
# ---------------------------------------------------------------------------
def gmail_client(user_email: str) -> Any:
    return build_service("gmail", "v1", subject=user_email)


def drive_client(subject: str | None = None) -> Any:
    return build_service("drive", "v3", subject=subject)


def calendar_client(user_email: str) -> Any:
    return build_service("calendar", "v3", subject=user_email)


def docs_client(subject: str | None = None) -> Any:
    return build_service("docs", "v1", subject=subject)


def sheets_client(subject: str | None = None) -> Any:
    return build_service("sheets", "v4", subject=subject)


def slides_client(subject: str | None = None) -> Any:
    return build_service("slides", "v1", subject=subject)


def directory_client(subject: str | None = None) -> Any:
    """Admin SDK Directory — must impersonate a Workspace admin."""
    return build_service("admin", "directory_v1", subject=subject)


def reports_client(subject: str | None = None) -> Any:
    """Admin SDK Reports — audit + usage logs. Admin impersonation required."""
    return build_service("admin", "reports_v1", subject=subject)


def people_client(subject: str | None = None) -> Any:
    return build_service("people", "v1", subject=subject)


def tasks_client(user_email: str) -> Any:
    return build_service("tasks", "v1", subject=user_email)


# ---------------------------------------------------------------------------
# MCPIntegration adapter — fits the existing dispatch pattern
# ---------------------------------------------------------------------------
class GoogleWorkspaceDWDIntegration(MCPIntegration):
    """Adapter for the existing MCP dispatcher.

    DWD has no OAuth flow, so authorization_url / exchange_code / refresh_tokens
    are intentionally inert. ``call`` dispatches to a small set of pre-defined
    read-only tools by name.
    """

    provider = "google_workspace_dwd"

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError("DWD does not use per-user OAuth")

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        raise NotImplementedError("DWD does not use per-user OAuth")

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        # SA credentials self-refresh; expose stable shape for audit consistency
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            handler = _TOOL_REGISTRY.get(tool)
            if handler is None:
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
            data = handler(params)
            return MCPCallResult(ok=True, data=data)
        except Exception as exc:
            logger.exception("DWD tool %s failed", tool)
            return MCPCallResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Tool handlers — small, composable, unit-testable
# ---------------------------------------------------------------------------
def _tool_list_users(params: dict[str, Any]) -> dict[str, Any]:
    domain = params.get("domain") or settings.GOOGLE_WORKSPACE_DOMAIN
    page_token = params.get("page_token")
    svc = directory_client()
    req = svc.users().list(domain=domain, maxResults=200, pageToken=page_token, orderBy="email")
    resp = req.execute()
    return {
        "users": resp.get("users", []),
        "next_page_token": resp.get("nextPageToken"),
    }


def _tool_list_drive_files(params: dict[str, Any]) -> dict[str, Any]:
    page_token = params.get("page_token")
    q = params.get("q", "")
    fields = (
        "nextPageToken, files("
        "id, name, mimeType, owners, modifiedTime, parents, size, webViewLink, trashed)"
    )
    svc = drive_client()
    req = svc.files().list(
        corpora="domain",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        q=q,
        fields=fields,
        pageSize=1000,
        pageToken=page_token,
    )
    resp = req.execute()
    return {
        "files": resp.get("files", []),
        "next_page_token": resp.get("nextPageToken"),
    }


def _tool_get_drive_changes(params: dict[str, Any]) -> dict[str, Any]:
    page_token = params["page_token"]
    svc = drive_client()
    req = svc.changes().list(
        pageToken=page_token,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        includeRemoved=True,
        fields=(
            "newStartPageToken, nextPageToken, "
            "changes(removed, fileId, file(id, name, mimeType, owners, modifiedTime, "
            "size, webViewLink, trashed))"
        ),
    )
    resp = req.execute()
    return {
        "changes": resp.get("changes", []),
        "next_page_token": resp.get("nextPageToken"),
        "new_start_page_token": resp.get("newStartPageToken"),
    }


def _tool_drive_start_page_token(params: dict[str, Any]) -> dict[str, Any]:
    svc = drive_client()
    resp = svc.changes().getStartPageToken(supportsAllDrives=True).execute()
    return {"start_page_token": resp.get("startPageToken")}


_TOOL_REGISTRY = {
    "list_users": _tool_list_users,
    "list_drive_files": _tool_list_drive_files,
    "get_drive_changes": _tool_get_drive_changes,
    "drive_start_page_token": _tool_drive_start_page_token,
}
