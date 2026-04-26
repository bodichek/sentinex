"""LLM Gateway — single chokepoint for every Anthropic call.

No code outside this module imports the Anthropic SDK directly. Handles
model routing, exact-match Redis caching, retries with exponential backoff,
cost accounting, and per-tenant usage logging.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from decimal import Decimal as _Decimal
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

import anthropic
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)
from django.conf import settings
from django.core.cache import cache
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.agents.pricing import compute_cost_czk, resolve_model
from apps.core.models import LLMUsage, Tenant

logger = logging.getLogger(__name__)
llm_logger = logging.getLogger("sentinex.llm")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_czk: Decimal
    cached: bool
    latency_ms: int
    stop_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMGatewayError(Exception):
    """Base class for LLM Gateway errors."""


class LLMAuthError(LLMGatewayError):
    """API key invalid or missing."""


class LLMRateLimitError(LLMGatewayError):
    """Upstream rate limit, retries exhausted."""


class LLMUnavailableError(LLMGatewayError):
    """Connection / 5xx upstream errors after retries."""


# ---------------------------------------------------------------------------
# Client (lazy singleton)
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise LLMAuthError("ANTHROPIC_API_KEY is not configured.")
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_key(model: str, temperature: float, prompt: str, system: str | None) -> str:
    payload = json.dumps(
        {"m": model, "t": temperature, "p": prompt, "s": system or ""},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"llm:{digest}"


# ---------------------------------------------------------------------------
# Upstream call with retries
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _call_anthropic(
    *,
    model: str,
    prompt: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
) -> anthropic.types.Message:
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    result: anthropic.types.Message = _get_client().messages.create(**kwargs)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


ModelAlias = Literal["sonnet", "haiku", "opus"]


def complete(
    prompt: str,
    *,
    model: str = "sonnet",
    system: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    cache_ttl: int | None = None,
    tenant: Tenant | None = None,
) -> LLMResponse:
    """Generate a completion, routing through cache + retries + cost logging."""
    resolved = resolve_model(model)
    cache_on = bool(settings.LLM_CACHE_ENABLED) and (cache_ttl is None or cache_ttl > 0)
    ttl = cache_ttl if cache_ttl is not None else int(settings.LLM_CACHE_DEFAULT_TTL)
    key = _cache_key(resolved, temperature, prompt, system)

    if cache_on:
        cached = cache.get(key)
        if cached is not None:
            response = LLMResponse(**cached, cached=True, latency_ms=0)
            _record_usage(response, tenant, key)
            return response

    start = time.monotonic()
    try:
        message = _call_anthropic(
            model=resolved,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except AuthenticationError as exc:
        raise LLMAuthError(str(exc)) from exc
    except RateLimitError as exc:
        raise LLMRateLimitError(str(exc)) from exc
    except (APIConnectionError, APIStatusError, RetryError) as exc:
        raise LLMUnavailableError(str(exc)) from exc

    latency_ms = int((time.monotonic() - start) * 1000)
    content = "".join(block.text for block in message.content if block.type == "text")
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    cost = compute_cost_czk(resolved, input_tokens, output_tokens)

    response = LLMResponse(
        content=content,
        model=resolved,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_czk=cost,
        cached=False,
        latency_ms=latency_ms,
        stop_reason=message.stop_reason,
    )

    if cache_on:
        cache.set(
            key,
            {
                "content": content,
                "model": resolved,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_czk": cost,
                "stop_reason": message.stop_reason,
                "raw": {},
            },
            ttl,
        )

    _record_usage(response, tenant, key)
    _emit_llm_event(response, tenant)
    return response


def _emit_llm_event(response: LLMResponse, tenant: Tenant | None) -> None:
    czk_per_usd = float(getattr(settings, "USD_TO_CZK", 24.0)) or 24.0
    cost_usd = float(response.cost_czk) / czk_per_usd if response.cost_czk else 0.0
    payload = {
        "event": "llm_call",
        "tenant": getattr(tenant, "schema_name", None),
        "model": response.model,
        "tokens": response.input_tokens + response.output_tokens,
        "cost_usd": round(cost_usd, 6),
        "latency_ms": response.latency_ms,
        "cached": response.cached,
    }
    llm_logger.info(json.dumps(payload, default=_json_default))


def _json_default(value: object) -> object:
    if isinstance(value, _Decimal):
        return float(value)
    return str(value)


def _record_usage(response: LLMResponse, tenant: Tenant | None, key: str) -> None:
    LLMUsage.objects.create(
        tenant=tenant,
        model=response.model,
        prompt_hash=key.removeprefix("llm:"),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_czk=response.cost_czk,
        cached=response.cached,
        latency_ms=response.latency_ms,
    )
