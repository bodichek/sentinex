"""Google Sheets → flattened tab-separated text via Sheets API."""

from __future__ import annotations

from typing import Any

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import sheets_client

MIME_GSHEET = "application/vnd.google-apps.spreadsheet"
MAX_ROWS_PER_SHEET = 5000


@register(MIME_GSHEET)
def extract_google_sheet(file_meta: dict[str, Any]) -> ExtractionResult:
    file_id = file_meta["id"]
    svc = sheets_client()
    meta = svc.spreadsheets().get(spreadsheetId=file_id, includeGridData=False).execute()
    parts: list[str] = []
    truncated = False
    for sheet in meta.get("sheets", []):
        title = sheet["properties"]["title"]
        rng = f"'{title}'!A1:Z{MAX_ROWS_PER_SHEET}"
        values_resp = (
            svc.spreadsheets().values().get(spreadsheetId=file_id, range=rng).execute()
        )
        values = values_resp.get("values", [])
        if len(values) >= MAX_ROWS_PER_SHEET:
            truncated = True
        parts.append(f"# Sheet: {title}")
        for row in values:
            parts.append("\t".join(str(c) for c in row))
        parts.append("")
    return ExtractionResult(
        text="\n".join(parts),
        truncated=truncated,
        metadata={"extractor": "google_sheets"},
    )
