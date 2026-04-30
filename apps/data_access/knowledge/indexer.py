"""End-to-end ingestion of a single Workspace artifact: extract → chunk → embed → store."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.db import connection, transaction
from django.utils import timezone

from apps.data_access.knowledge.chunker import chunk_text
from apps.data_access.knowledge.embedder import embed_texts
from apps.data_access.knowledge.extractors import extract
from apps.data_access.models import WorkspaceDocument

logger = logging.getLogger(__name__)


GOOGLE_NATIVE_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}
TEXTUAL_MIMES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "application/pdf",
}
SUPPORTED_MIMES = GOOGLE_NATIVE_MIMES | TEXTUAL_MIMES


def _delete_chunks(document_id: int) -> None:
    with connection.cursor() as cur:
        cur.execute(
            "DELETE FROM data_access_knowledgechunk WHERE document_id = %s",
            [document_id],
        )


def _insert_chunks(document_id: int, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with connection.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO data_access_knowledgechunk
                    (id, document_id, chunk_index, text, token_count, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::vector, %s::jsonb)
                """,
                [
                    str(row["id"]),
                    document_id,
                    row["chunk_index"],
                    row["text"],
                    row["token_count"],
                    row["embedding_literal"],
                    row["metadata_json"],
                ],
            )


def upsert_drive_file(file_meta: dict[str, Any]) -> WorkspaceDocument:
    """Create/update a WorkspaceDocument row from a Drive ``files.list`` entry."""
    owners = file_meta.get("owners") or []
    owner_email = owners[0].get("emailAddress", "") if owners else ""
    doc, _ = WorkspaceDocument.objects.update_or_create(
        source=WorkspaceDocument.SOURCE_DRIVE,
        external_id=file_meta["id"],
        defaults={
            "title": file_meta.get("name", "")[:512],
            "mime_type": file_meta.get("mimeType", "")[:128],
            "owner_email": owner_email[:254],
            "web_view_link": file_meta.get("webViewLink", "")[:1024],
            "modified_at": file_meta.get("modifiedTime"),
            "size_bytes": int(file_meta.get("size") or 0),
            "metadata": {"parents": file_meta.get("parents", [])},
        },
    )
    return doc


def remove_document(source: str, external_id: str) -> None:
    qs = WorkspaceDocument.objects.filter(source=source, external_id=external_id)
    for doc in qs:
        _delete_chunks(doc.pk)
    qs.delete()


def ingest_document(document: WorkspaceDocument, file_meta: dict[str, Any]) -> str:
    """Extract → chunk → embed → upsert. Returns final status."""
    if document.mime_type not in SUPPORTED_MIMES:
        document.status = WorkspaceDocument.STATUS_SKIPPED
        document.error = f"unsupported mime: {document.mime_type}"
        document.save(update_fields=["status", "error", "updated_at"])
        return document.status

    try:
        result = extract(document.mime_type, file_meta)
    except Exception as exc:
        logger.exception("extract failed for %s", document.external_id)
        document.status = WorkspaceDocument.STATUS_FAILED
        document.error = str(exc)[:500]
        document.save(update_fields=["status", "error", "updated_at"])
        return document.status

    if result is None or not result.text.strip():
        document.status = WorkspaceDocument.STATUS_SKIPPED
        document.error = "empty content"
        document.save(update_fields=["status", "error", "updated_at"])
        return document.status

    document.text_content = result.text[:1_000_000]  # safety cap on raw column
    document.text_truncated = result.truncated
    document.status = WorkspaceDocument.STATUS_EXTRACTED
    document.extracted_at = timezone.now()
    extra_meta = dict(document.metadata or {})
    extra_meta.update(result.metadata)
    document.metadata = extra_meta
    document.save()

    chunks = chunk_text(result.text)
    if not chunks:
        document.status = WorkspaceDocument.STATUS_SKIPPED
        document.error = "no chunks"
        document.save(update_fields=["status", "error", "updated_at"])
        return document.status

    embeddings = embed_texts([c.text for c in chunks])
    rows: list[dict[str, Any]] = []
    import json as _json

    for c, emb in zip(chunks, embeddings, strict=False):
        rows.append(
            {
                "id": uuid.uuid4(),
                "chunk_index": c.index,
                "text": c.text,
                "token_count": c.token_count,
                "embedding_literal": "[" + ",".join(f"{x:.6f}" for x in emb) + "]",
                "metadata_json": _json.dumps(
                    {
                        "title": document.title,
                        "owner_email": document.owner_email,
                        "web_view_link": document.web_view_link,
                        "mime_type": document.mime_type,
                        "source": document.source,
                    }
                ),
            }
        )

    with transaction.atomic():
        _delete_chunks(document.pk)
        _insert_chunks(document.pk, rows)
        document.status = WorkspaceDocument.STATUS_INDEXED
        document.indexed_at = timezone.now()
        document.error = ""
        document.save(update_fields=["status", "indexed_at", "error", "updated_at"])
    return document.status
