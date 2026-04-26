"""Embedding Gateway — single chokepoint for OpenAI embedding calls.

Mirrors the LLM Gateway pattern: lazy client, exact-match Redis cache, retries,
cost accounting + structured JSON log. Returns a list of float vectors aligned
with the input order. Cached entries are reused; only the cache misses go to
the upstream API in a single batch call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
embedding_logger = logging.getLogger("sentinex.llm")

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
MAX_BATCH = 100
CACHE_TTL_SECONDS = 7 * 24 * 3600

# USD per 1M tokens (text-embedding-3-small as of 2026-01).
PRICE_USD_PER_MILLION_TOKENS = Decimal("0.020")


class EmbeddingGatewayError(Exception):
    """Base error for the embedding gateway."""


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: list[list[float]]
    model: str
    cached_count: int
    fetched_count: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Client (lazy singleton)
# ---------------------------------------------------------------------------

_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise EmbeddingGatewayError("openai SDK not installed") from exc
        if not getattr(settings, "OPENAI_API_KEY", ""):
            raise EmbeddingGatewayError("OPENAI_API_KEY is not configured")
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_key(model: str, text: str) -> str:
    digest = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:16]
    return f"emb:{model}:{digest}"


# ---------------------------------------------------------------------------
# Upstream call
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_openai(model: str, batch: list[str]) -> Any:
    return _get_client().embeddings.create(model=model, input=batch)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def embed(
    texts: list[str],
    *,
    model: str = DEFAULT_MODEL,
    tenant: Any | None = None,
    use_cache: bool = True,
) -> EmbeddingResponse:
    """Embed a batch of texts. Honors a 100-item upstream batch limit."""
    if not texts:
        return EmbeddingResponse(
            vectors=[],
            model=model,
            cached_count=0,
            fetched_count=0,
            total_tokens=0,
            cost_usd=Decimal("0"),
            latency_ms=0,
        )

    n = len(texts)
    vectors: list[list[float] | None] = [None] * n
    misses: list[tuple[int, str]] = []

    if use_cache:
        for i, text in enumerate(texts):
            cached = cache.get(_cache_key(model, text))
            if cached is not None:
                vectors[i] = list(cached)
            else:
                misses.append((i, text))
    else:
        misses = list(enumerate(texts))

    cached_count = n - len(misses)
    total_tokens = 0
    start = time.monotonic()

    for chunk_start in range(0, len(misses), MAX_BATCH):
        chunk = misses[chunk_start : chunk_start + MAX_BATCH]
        batch_texts = [t for _, t in chunk]
        result = _call_openai(model, batch_texts)
        for (orig_index, text), item in zip(chunk, result.data, strict=True):
            vector = list(item.embedding)
            vectors[orig_index] = vector
            if use_cache:
                cache.set(_cache_key(model, text), vector, CACHE_TTL_SECONDS)
        total_tokens += int(getattr(result.usage, "total_tokens", 0) or 0)

    latency_ms = int((time.monotonic() - start) * 1000)
    cost_usd = (
        Decimal(total_tokens) * PRICE_USD_PER_MILLION_TOKENS / Decimal(1_000_000)
    ).quantize(Decimal("0.000001"))

    final_vectors = [v if v is not None else [] for v in vectors]
    response = EmbeddingResponse(
        vectors=final_vectors,
        model=model,
        cached_count=cached_count,
        fetched_count=len(misses),
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    _emit_event(response, tenant)
    return response


def _emit_event(response: EmbeddingResponse, tenant: Any | None) -> None:
    payload = {
        "event": "embedding",
        "tenant": getattr(tenant, "schema_name", None),
        "model": response.model,
        "texts": response.cached_count + response.fetched_count,
        "cached": response.cached_count,
        "cost_usd": float(response.cost_usd),
        "latency_ms": response.latency_ms,
    }
    embedding_logger.info(json.dumps(payload))
