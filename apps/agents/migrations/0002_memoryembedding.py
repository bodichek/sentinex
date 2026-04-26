"""Create pgvector extension + agents_memoryembedding table (tenant schema only).

The migration probes ``pg_available_extensions`` first; on dev / CI runs without
the pgvector library installed in Postgres, the migration becomes a no-op so
the rest of the test suite still runs.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agents_memoryembedding (
    id uuid PRIMARY KEY,
    tenant_user_id bigint NULL,
    source varchar(32) NOT NULL,
    content text NOT NULL,
    embedding vector(1536),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agents_memoryembedding_source_idx
    ON agents_memoryembedding (source);
CREATE INDEX IF NOT EXISTS agents_memoryembedding_embedding_ivfflat_idx
    ON agents_memoryembedding USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

DROP_SQL = "DROP TABLE IF EXISTS agents_memoryembedding"


def forwards(apps: Any, schema_editor: Any) -> None:
    conn = schema_editor.connection
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        if cur.fetchone() is None:
            return
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(CREATE_TABLE_SQL)


def reverse(apps: Any, schema_editor: Any) -> None:
    with schema_editor.connection.cursor() as cur:
        cur.execute(DROP_SQL)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("agents", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
