"""Gmail message → headers + body plain text."""

from __future__ import annotations

import base64
from typing import Any

from apps.data_access.knowledge.extractors.base import ExtractionResult, register
from apps.data_access.mcp.integrations.google_workspace_dwd import gmail_client


def _walk_parts(part: dict[str, Any]) -> str:
    if part.get("mimeType") == "text/plain":
        data = part.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
    out = ""
    for sub in part.get("parts", []) or []:
        out += _walk_parts(sub)
    return out


@register("gmail/message")
def extract_gmail_message(file_meta: dict[str, Any]) -> ExtractionResult:
    """``file_meta`` must include ``user_email`` and ``id`` (Gmail messageId)."""
    user_email = file_meta["user_email"]
    msg_id = file_meta["id"]
    svc = gmail_client(user_email)
    msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {
        h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])
    }
    body = _walk_parts(msg.get("payload", {}))
    text = (
        f"From: {headers.get('from', '')}\n"
        f"To: {headers.get('to', '')}\n"
        f"Subject: {headers.get('subject', '')}\n"
        f"Date: {headers.get('date', '')}\n\n"
        f"{body}"
    )
    return ExtractionResult(
        text=text,
        metadata={
            "extractor": "gmail",
            "thread_id": msg.get("threadId"),
            "labels": msg.get("labelIds", []),
        },
    )
