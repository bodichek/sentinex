"""Google Docs → plain text via Drive export."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import drive_client

MIME_GDOC = "application/vnd.google-apps.document"


@register(MIME_GDOC)
def extract_google_doc(file_meta: dict[str, Any]) -> ExtractionResult:
    file_id = file_meta["id"]
    svc = drive_client()
    resp = svc.files().export(fileId=file_id, mimeType="text/plain").execute()
    text = resp.decode("utf-8") if isinstance(resp, bytes) else str(resp)
    max_bytes = settings.KNOWLEDGE_MAX_FILE_BYTES
    truncated = False
    if len(text.encode("utf-8")) > max_bytes:
        text = text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        truncated = True
    return ExtractionResult(text=text, truncated=truncated, metadata={"extractor": "google_docs"})
