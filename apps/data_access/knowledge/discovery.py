"""Discovery: enumerate every Drive file in the Workspace domain."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from apps.data_access.mcp.integrations.google_workspace_dwd import drive_client

logger = logging.getLogger(__name__)

DRIVE_LIST_FIELDS = (
    "nextPageToken, files("
    "id, name, mimeType, owners, modifiedTime, parents, size, webViewLink, trashed)"
)


def iter_drive_files(query: str = "") -> Iterator[dict[str, Any]]:
    """Yield every Drive file in the domain (excluding trashed)."""
    svc = drive_client()
    page_token: str | None = None
    full_query = "trashed = false"
    if query:
        full_query = f"{full_query} and ({query})"
    while True:
        resp = (
            svc.files()
            .list(
                corpora="domain",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                q=full_query,
                fields=DRIVE_LIST_FIELDS,
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )
        for f in resp.get("files", []):
            if f.get("trashed"):
                continue
            yield f
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def get_start_page_token() -> str:
    svc = drive_client()
    resp = svc.changes().getStartPageToken(supportsAllDrives=True).execute()
    return str(resp["startPageToken"])


def iter_drive_changes(page_token: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Drain Drive Changes API from ``page_token``.

    Returns: (changes, next_page_token, new_start_page_token).
    Caller persists ``new_start_page_token`` (when set) as the next watermark.
    """
    svc = drive_client()
    all_changes: list[dict[str, Any]] = []
    next_token: str | None = page_token
    new_start: str | None = None
    while next_token:
        resp = (
            svc.changes()
            .list(
                pageToken=next_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                includeRemoved=True,
                fields=(
                    "newStartPageToken, nextPageToken, "
                    "changes(removed, fileId, file(id, name, mimeType, owners, "
                    "modifiedTime, size, webViewLink, trashed))"
                ),
            )
            .execute()
        )
        all_changes.extend(resp.get("changes", []))
        next_token = resp.get("nextPageToken")
        # Drain ``nextPageToken`` first; only persist the watermark when we
        # have truly reached the end of the change stream (no more pages).
        if next_token:
            continue
        new_start = resp.get("newStartPageToken")
        break
    return all_changes, next_token, new_start
