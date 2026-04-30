"""Semantic search over indexed knowledge chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import connection

from apps.data_access.knowledge.embedder import embed_query


@dataclass
class SearchHit:
    chunk_id: str
    document_id: int
    chunk_index: int
    text: str
    similarity: float
    metadata: dict[str, Any]


def search_chunks(
    query: str,
    top_k: int = 10,
    source: str | None = None,
    owner_email: str | None = None,
) -> list[SearchHit]:
    """Cosine-similarity top-K retrieval over data_access_knowledgechunk."""
    if not query.strip():
        return []
    q_emb = embed_query(query)
    emb_literal = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"

    where_clauses: list[str] = []
    params: list[Any] = [emb_literal]
    if source:
        where_clauses.append("d.source = %s")
        params.append(source)
    if owner_email:
        where_clauses.append("d.owner_email = %s")
        params.append(owner_email)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.extend([emb_literal, top_k])

    sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.text, c.metadata,
               1 - (c.embedding <=> %s::vector) AS similarity
          FROM data_access_knowledgechunk c
          JOIN data_access_workspacedocument d ON d.id = c.document_id
        {where_sql}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """
    hits: list[SearchHit] = []
    with connection.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            chunk_id, doc_id, idx, text, meta, sim = row
            hits.append(
                SearchHit(
                    chunk_id=str(chunk_id),
                    document_id=doc_id,
                    chunk_index=idx,
                    text=text,
                    similarity=float(sim),
                    metadata=meta or {},
                )
            )
    return hits


def format_hits_for_prompt(hits: list[SearchHit]) -> str:
    """Render hits as numbered citations for inclusion in an LLM prompt."""
    out: list[str] = []
    for i, h in enumerate(hits, start=1):
        title = h.metadata.get("title", "(untitled)")
        url = h.metadata.get("web_view_link", "")
        out.append(f"[{i}] {title} — {url}\n{h.text}\n")
    return "\n---\n".join(out)
