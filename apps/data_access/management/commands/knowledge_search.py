"""CLI smoke-test for the knowledge search index.

Example:
    python manage.py knowledge_search --tenant=acme --query="cenotvorba 2026"
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Run a semantic search against the knowledge index for a tenant."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--query", required=True)
        parser.add_argument("--top-k", type=int, default=5)

    def handle(self, *args: Any, **opts: Any) -> None:
        from apps.data_access.knowledge.search import search_chunks

        with schema_context(opts["tenant"]):
            hits = search_chunks(opts["query"], top_k=opts["top_k"])

        if not hits:
            self.stdout.write("No matches.")
            return
        for i, h in enumerate(hits, start=1):
            title = h.metadata.get("title", "(untitled)")
            url = h.metadata.get("web_view_link", "")
            self.stdout.write(
                self.style.NOTICE(f"\n[{i}] sim={h.similarity:.3f}  {title}\n    {url}")
            )
            preview = h.text.strip().replace("\n", " ")[:240]
            self.stdout.write(f"    {preview}")
