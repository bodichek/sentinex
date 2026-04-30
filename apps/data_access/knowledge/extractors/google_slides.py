"""Google Slides → text via Slides API (slide-by-slide, all text runs)."""

from __future__ import annotations

from typing import Any

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import slides_client

MIME_GSLIDES = "application/vnd.google-apps.presentation"


def _walk_text(element: dict[str, Any]) -> list[str]:
    out: list[str] = []
    text_el = element.get("shape", {}).get("text") or element.get("text")
    if text_el:
        for te in text_el.get("textElements", []):
            run = te.get("textRun") or {}
            content = run.get("content")
            if content:
                out.append(content)
    return out


@register(MIME_GSLIDES)
def extract_google_slides(file_meta: dict[str, Any]) -> ExtractionResult:
    file_id = file_meta["id"]
    svc = slides_client()
    pres = svc.presentations().get(presentationId=file_id).execute()
    parts: list[str] = []
    for i, slide in enumerate(pres.get("slides", []), start=1):
        parts.append(f"# Slide {i}")
        for el in slide.get("pageElements", []):
            parts.extend(_walk_text(el))
        parts.append("")
    return ExtractionResult(text="\n".join(parts), metadata={"extractor": "google_slides"})
