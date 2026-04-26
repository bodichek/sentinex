# Prompt 04: LLM Gateway

## Goal

Build the LLM Gateway — a thin, unified wrapper over the Anthropic SDK that handles model routing (Sonnet/Haiku), token counting, exact-match caching, retries, and per-tenant cost tracking.

## Prerequisites

- Prompts 01–03 complete
- `ANTHROPIC_API_KEY` in `.env`
- Redis running

## Context

Every LLM call in Sentinex goes through the Gateway. No code anywhere else imports the Anthropic SDK directly. This gives us a single chokepoint for cost control, caching, observability, and future multi-provider support.

See `docs/AGENTS.md` section "LLM Gateway" for full design.

## Constraints

- Only Anthropic SDK in MVP (no OpenAI for LLM, only for embeddings)
- No direct `anthropic.Anthropic()` usage outside the gateway
- Caching is exact-match (hash of prompt + model + temperature)
- Cache TTL configurable per call (default 1 hour)
- Token counting persisted per tenant for billing
- Retries: exponential backoff on rate limits, no retry on auth errors

## Deliverables

1. `apps/agents/` Django app created
2. `apps/agents/llm_gateway.py` with:
   - `complete(prompt, model="sonnet", temperature=0.3, max_tokens=4096, cache_ttl=3600) -> LLMResponse`
   - `LLMResponse` dataclass with `content`, `model`, `usage`, `cached`, `latency_ms`
   - Exact-match cache via Redis
   - Retry logic with exponential backoff (use `tenacity` or similar)
   - Error handling (wrap Anthropic errors in custom exceptions)
3. `apps/agents/models.py`:
   - `LLMUsage` model (tenant-aware) logging every call
   - Fields: tenant, model, input_tokens, output_tokens, cost_czk, cached, latency_ms, created_at
4. Pricing table in `apps/agents/pricing.py` with current per-million-token costs for Sonnet and Haiku
5. Model router function that selects Sonnet or Haiku based on task complexity hint
6. Configuration in settings for:
   - `ANTHROPIC_API_KEY`
   - `LLM_DEFAULT_MODEL`
   - `LLM_CACHE_ENABLED`
   - `LLM_CACHE_DEFAULT_TTL`
7. Admin registration for LLMUsage (read-only, filterable by tenant)
8. Unit tests:
   - Cache hit returns cached response
   - Cache miss calls API
   - Token counting correct
   - Retry on rate limit
   - Error on auth failure
9. Integration test (marked `@pytest.mark.integration`):
   - Real API call with short prompt, verify structure

## Acceptance Criteria

- `from apps.agents.llm_gateway import complete` works from any app
- Calling `complete("hello world", model="haiku")` returns real LLM response
- Second identical call returns cached response (check `response.cached == True`)
- `LLMUsage` records visible in admin after calls
- Total cost accumulates per tenant in admin
- Tests pass (unit tests without API key, integration tests with real key)
- `mypy` strict passes on `apps/agents/llm_gateway.py`

## Next Steps

After this prompt, proceed to `05-agent-layer.md`.

## Notes for Claude Code

- Use `anthropic` official Python SDK
- Model names: `claude-sonnet-4-20250514` (or latest), `claude-haiku-4-5-20251001`
- Use Redis for cache (already running from prompt 01)
- Cache key: `sha256(model + temperature + prompt)` — include all params that affect output
- Don't cache if `cache_ttl=0`
- Log every call to `LLMUsage` even if cached (mark `cached=True`)
- Pricing: Sonnet roughly $3/million input, $15/million output (verify current pricing)
- Convert cost to CZK using a fixed rate (or env variable `USD_TO_CZK`)
- Use structured logging (include model, tenant_id, latency)
