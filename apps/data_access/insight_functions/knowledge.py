"""Insight functions backed by the Workspace knowledge index."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from apps.data_access.knowledge.search import format_hits_for_prompt, search_chunks


@dataclass
class KnowledgeAnswerContext:
    query: str
    hits: list[dict[str, Any]]
    prompt_context: str


def search_company_knowledge(
    query: str,
    top_k: int = 8,
    source: str | None = None,
    owner_email: str | None = None,
) -> KnowledgeAnswerContext:
    """Retrieve top-K most relevant chunks for ``query`` from the knowledge index.

    Returns both the structured hits (for UI rendering) and a pre-formatted
    prompt_context block (drop-in for LLM system prompts with citations).
    """
    hits = search_chunks(query, top_k=top_k, source=source, owner_email=owner_email)
    return KnowledgeAnswerContext(
        query=query,
        hits=[asdict(h) for h in hits],
        prompt_context=format_hits_for_prompt(hits),
    )
