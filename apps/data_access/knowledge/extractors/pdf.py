"""PDF / DOCX / generic-binary → text via Drive download + pypdf.

For Office files (DOCX/XLSX/PPTX) we let Drive export them as Google formats
which then go through the gdoc extractor on a re-pass; this extractor only
covers raw application/pdf and similar.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from django.conf import settings

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import drive_client

logger = logging.getLogger(__name__)

MIME_PDF = "application/pdf"


@register(MIME_PDF)
def extract_pdf(file_meta: dict[str, Any]) -> ExtractionResult:
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-not-found]
    from pypdf import PdfReader  # type: ignore[import-not-found]

    file_id = file_meta["id"]
    size = int(file_meta.get("size") or 0)
    if size and size > settings.KNOWLEDGE_MAX_FILE_BYTES:
        return ExtractionResult(
            text="", truncated=True, metadata={"extractor": "pdf", "skipped": "too_large"}
        )

    svc = drive_client()
    request = svc.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()

    buffer.seek(0)
    try:
        reader = PdfReader(buffer)
    except Exception as exc:
        logger.warning("PDF parse failed for %s: %s", file_id, exc)
        return ExtractionResult(
            text="", metadata={"extractor": "pdf", "error": str(exc)[:200]}
        )

    parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            parts.append(f"# Page {i}")
            parts.append(page.extract_text() or "")
            parts.append("")
        except Exception as exc:
            logger.debug("page extract failed: %s", exc)
    return ExtractionResult(text="\n".join(parts), metadata={"extractor": "pdf"})
