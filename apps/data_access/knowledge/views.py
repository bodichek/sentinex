"""Knowledge search UI — full page + HTMX result fragment."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.core.middleware import require_membership
from apps.data_access.knowledge.search import search_chunks


@login_required
@require_membership
def knowledge_search(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    top_k = int(request.GET.get("k") or 8)
    hits: list = []
    error = ""
    if query:
        try:
            hits = search_chunks(query, top_k=top_k)
        except Exception as exc:
            error = str(exc)

    template = (
        "knowledge/_results.html" if request.headers.get("HX-Request") else "knowledge/search.html"
    )
    return render(
        request,
        template,
        {"query": query, "top_k": top_k, "hits": hits, "error": error},
    )
