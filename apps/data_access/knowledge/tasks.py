"""Celery tasks for Workspace knowledge ingestion."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.data_access.knowledge import discovery
from apps.data_access.knowledge.indexer import (
    SUPPORTED_MIMES,
    ingest_document,
    remove_document,
    upsert_drive_file,
)
from apps.data_access.models import IngestionCursor, WorkspaceDocument

logger = logging.getLogger(__name__)

DRIVE_CURSOR_KEY = "drive_changes"


@shared_task
def ingest_drive_file(file_meta: dict[str, Any]) -> dict[str, Any]:
    """Ingest one Drive file end-to-end. Idempotent."""
    doc = upsert_drive_file(file_meta)
    if doc.mime_type not in SUPPORTED_MIMES:
        doc.status = WorkspaceDocument.STATUS_SKIPPED
        doc.error = f"unsupported mime: {doc.mime_type}"
        doc.save(update_fields=["status", "error", "updated_at"])
        return {"id": doc.external_id, "status": doc.status}
    status = ingest_document(doc, file_meta)
    return {"id": doc.external_id, "status": status}


@shared_task
def full_ingest_workspace() -> dict[str, Any]:
    """Initial bulk index of every Drive file in the domain.

    Streams the ``files.list`` paginated result into ``ingest_drive_file`` tasks
    so workers can fan out. Updates the IngestionCursor when complete.
    """
    cursor, _ = IngestionCursor.objects.get_or_create(source=DRIVE_CURSOR_KEY)
    # Capture starting page token BEFORE listing — anything created during full
    # sync is then picked up by the next incremental run.
    start_token = discovery.get_start_page_token()

    total = 0
    queued = 0
    for f in discovery.iter_drive_files():
        total += 1
        if f.get("mimeType") in SUPPORTED_MIMES:
            ingest_drive_file.delay(f)
            queued += 1
        else:
            # Still record metadata so we know it exists
            upsert_drive_file(f)

    cursor.cursor = start_token
    cursor.last_full_sync_at = timezone.now()
    cursor.files_total = total
    cursor.save()
    return {"total": total, "queued": queued, "start_token": start_token}


@shared_task
def incremental_ingest_workspace() -> dict[str, Any]:
    """Apply Drive Changes API delta from the persisted cursor."""
    cursor = IngestionCursor.objects.filter(source=DRIVE_CURSOR_KEY).first()
    if cursor is None or not cursor.cursor:
        logger.info("incremental_ingest: no cursor, falling back to full sync")
        return full_ingest_workspace()

    changes, next_token, new_start = discovery.iter_drive_changes(cursor.cursor)
    applied = 0
    removed = 0
    for ch in changes:
        if ch.get("removed") or (ch.get("file") or {}).get("trashed"):
            file_id = ch.get("fileId") or ch.get("file", {}).get("id")
            if file_id:
                remove_document(WorkspaceDocument.SOURCE_DRIVE, file_id)
                removed += 1
            continue
        f = ch.get("file") or {}
        if f and f.get("id"):
            ingest_drive_file.delay(f)
            applied += 1

    # Prefer the new watermark when reached; otherwise persist whatever
    # next_token we got so a partial drain can resume without losing pages.
    if new_start:
        cursor.cursor = new_start
    elif next_token:
        cursor.cursor = next_token
    cursor.last_incremental_sync_at = timezone.now()
    cursor.save()
    return {"applied": applied, "removed": removed, "new_token": cursor.cursor}
