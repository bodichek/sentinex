"""Plain text / markdown / CSV — straight Drive download."""

from __future__ import annotations

import io
from typing import Any

from django.conf import settings

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import drive_client


@register("text/plain", "text/markdown", "text/csv", "text/html")
def extract_plain_text(file_meta: dict[str, Any]) -> ExtractionResult:
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-not-found]

    file_id = file_meta["id"]
    max_bytes = settings.KNOWLEDGE_MAX_FILE_BYTES
    declared_size = int(file_meta.get("size") or 0)
    if declared_size and declared_size > max_bytes:
        return ExtractionResult(
            text="",
            truncated=True,
            metadata={
                "extractor": "plain_text",
                "mime": file_meta.get("mimeType"),
                "skipped_reason": f"file too large: {declared_size} > {max_bytes}",
            },
        )

    svc = drive_client()
    request = svc.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    truncated = False
    while not done:
        _status, done = downloader.next_chunk()
        if buffer.tell() > max_bytes:
            truncated = True
            break
    raw = buffer.getvalue()
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
        truncated = True
    text = raw.decode("utf-8", errors="ignore")
    return ExtractionResult(
        text=text,
        truncated=truncated,
        metadata={"extractor": "plain_text", "mime": file_meta.get("mimeType")},
    )
