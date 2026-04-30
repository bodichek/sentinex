"""Create pgvector-backed data_access_knowledgechunk table.

Mirrors the pattern in agents/0002_memoryembedding: probes for the ``vector``
extension and no-ops when not available so the rest of migrations still run.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import migrations

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_access_knowledgechunk (
    id uuid PRIMARY KEY,
    document_id bigint NOT NULL,
    chunk_index integer NOT NULL,
    text text NOT NULL,
    token_count integer NOT NULL DEFAULT 0,
    embedding vector({dim}),
    metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS data_access_knowledgechunk_doc_idx
    ON data_access_knowledgechunk (document_id);
CREATE INDEX IF NOT EXISTS data_access_knowledgechunk_emb_ivfflat_idx
    ON data_access_knowledgechunk USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

DROP_SQL = "DROP TABLE IF EXISTS data_access_knowledgechunk"


def forwards(apps: Any, schema_editor: Any) -> None:
    dim = getattr(settings, "KNOWLEDGE_EMBEDDING_DIMENSIONS", 1536)
    conn = schema_editor.connection
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        if cur.fetchone() is None:
            return
        # Pin the extension to ``public`` so its types resolve from the shared
        # schema regardless of which tenant search_path is active.
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")
        cur.execute(CREATE_TABLE_SQL.format(dim=dim))


def reverse(apps: Any, schema_editor: Any) -> None:
    with schema_editor.connection.cursor() as cur:
        cur.execute(DROP_SQL)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("data_access", "0004_workspace_document_and_cursor"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
