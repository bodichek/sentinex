# Prompt 06: Memory and Guardrails

## Goal

Implement the memory system (short, medium, long-term) and guardrails (cost budget, PII masking, scope check) that every agent invocation must pass through.

## Prerequisites

- Prompt 05 complete (Agent Layer works without memory/guardrails)

## Context

Memory gives agents context. Guardrails prevent abuse and leaks. Both are mandatory for production-grade AIOS.

See `docs/AGENTS.md` sections "Memory System" and "Guardrails".

## Constraints

- Memory is per-tenant, never cross-tenant
- Short-term: Redis with 2-hour TTL
- Medium-term: Postgres, 30-day retention
- Long-term: pgvector for RAG (Phase 2 populates it; scaffolding here)
- PII masking: regex-based for MVP
- All guardrails run synchronously before/after LLM calls

## Deliverables

1. `apps/agents/memory.py`:
   - `ShortTermMemory` class (Redis-backed, conversation-scoped)
   - `MediumTermMemory` class (Postgres, structured facts)
   - `LongTermMemory` class (pgvector RAG; interface only in this phase)
   - `MemoryManager` that aggregates all three
2. Models for medium-term:
   - `Conversation` (tenant-aware)
   - `ConversationMessage` (tenant-aware)
   - `ExtractedFact` (tenant-aware, for medium-term structured memory)
3. Models for long-term RAG (tenant-aware):
   - `Document`
   - `DocumentChunk` (with vector embedding)
4. `apps/agents/guardrails.py`:
   - `check_cost_budget(tenant, estimated_cost) -> CheckResult`
   - `check_scope(agent, requested_action) -> CheckResult`
   - `mask_pii(text) -> MaskedText`
   - `unmask_pii(text, mask_map) -> str`
   - `detect_prompt_injection(text) -> CheckResult`
   - `validate_output_format(text, expected_schema) -> CheckResult`
   - `log_for_compliance(tenant, agent, call_data)` (EU AI Act logging)
5. Orchestrator updated to invoke guardrails:
   - Pre-call: cost, scope, PII mask
   - Post-call: output validate, PII unmask, compliance log
6. Tenant budget model:
   - `TenantBudget` with monthly limit, current usage, per-conversation limit
7. Admin views for:
   - Conversation history per tenant
   - Budget monitoring per tenant
   - Compliance log
8. Management command `reset_tenant_budget` for monthly reset
9. Tests:
   - Memory write and read
   - Memory isolation between tenants
   - PII masking and unmasking
   - Cost budget enforcement
   - Prompt injection detection (basic cases)
   - Guardrails prevent over-budget calls

## Acceptance Criteria

- Agent queries create Conversation and ConversationMessage records
- Short-term memory survives within a single conversation
- PII in prompt (email, phone, name pattern) is masked before LLM call
- PII in response correctly unmasked for the authorized user
- Exceeding cost budget returns an error without calling LLM
- Compliance log shows every LLM call with required fields
- Tests pass

## Next Steps

After this prompt, Phase 1 is complete. Proceed to `phase-2-data-layer.md` → `07-google-workspace-mcp.md`.

## Notes for Claude Code

- PII masking patterns: email, phone (various formats), credit card, Czech birth number (rodné číslo)
- Keep mask tokens unique per conversation: `[EMAIL_0]`, `[EMAIL_1]`, etc.
- Store mask_map in Conversation model so unmasking works across turns
- Prompt injection detection: look for phrases like "ignore previous instructions", "you are now...", system prompt markers
- Budget check: query LLMUsage for current month, compare to TenantBudget
- pgvector setup: `CREATE EXTENSION IF NOT EXISTS vector;` in `setup_postgres` command
- Use `pgvector.django` package for vector field and similarity search
- Compliance log: timestamp, tenant, user, agent, model, prompt_hash (not full prompt), response_hash, success/error
- Don't log full prompts or responses for privacy; hash them for auditability
