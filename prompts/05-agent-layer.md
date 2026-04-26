# Prompt 05: Agent Layer Core

## Goal

Build the Agent Layer: Orchestrator that classifies intent and routes to Specialists. Implement 2 specialists (Strategic, Finance) with minimal functionality. Wire up context builder and prompt loading from YAML.

## Prerequisites

- Prompt 04 complete (LLM Gateway works)
- Celery configured (add if not)

## Context

The Agent Layer is the brain. Orchestrator receives a query, classifies intent, fans out to specialists in parallel, composes final response. Specialists have domain prompts in YAML, call the LLM Gateway, return structured outputs.

See `docs/AGENTS.md` for full design.

## Constraints

- Orchestrator is Claude Sonnet (reasoning-heavy)
- Specialists default to Sonnet, but can opt for Haiku per task
- Parallel execution via Celery `group` or `asyncio` (pick simpler for MVP: Celery group)
- System prompts in YAML, version-controlled
- No business data in prompts yet (comes in Phase 2)

## Deliverables

1. `apps/agents/base.py` with `BaseSpecialist` abstract class:
   - `name` class attribute
   - `system_prompt_file` class attribute
   - `analyze(context) -> SpecialistResponse` method
   - `SpecialistResponse` dataclass with `content`, `structured_data`, `confidence`
2. `apps/agents/prompts/` directory with YAML files:
   - `orchestrator.yaml`
   - `strategic_specialist.yaml`
   - `finance_specialist.yaml`
3. `apps/agents/prompt_loader.py` — load and cache YAML prompts
4. `apps/agents/specialists/`:
   - `strategic.py` — StrategicSpecialist
   - `finance.py` — FinanceSpecialist
5. `apps/agents/orchestrator.py` with `Orchestrator` class:
   - `classify_intent(query) -> Intent`
   - `select_specialists(intent) -> list[type[BaseSpecialist]]`
   - `handle(query, context) -> OrchestratorResponse` (main entry point)
6. `apps/agents/context_builder.py` — builds prompt context (basic for now)
7. `apps/agents/tasks.py` — Celery tasks for specialist invocation
8. Celery configuration in `config/celery.py`:
   - Celery app
   - Redis broker
   - Task discovery from apps
9. Management command `test_agent_query` that submits a query and prints response
10. View `POST /api/v1/query/` that accepts query and returns response
11. Tests:
    - Unit: orchestrator classifies intent correctly
    - Unit: specialist analyzes context and returns response
    - Integration: full query flow (query → orchestrator → specialists → composed response)

## Acceptance Criteria

- Running `poetry run celery -A config worker --loglevel=info` starts worker
- Running `test_agent_query "How's the business doing?"` returns LLM response
- API endpoint `POST /api/v1/query/` accepts JSON `{"query": "..."}` and returns response
- Parallel specialist execution visible in Celery logs
- Tests pass

## Next Steps

After this prompt, proceed to `06-memory-guardrails.md`.

## Notes for Claude Code

- Orchestrator YAML should instruct model to output JSON with `intent` and `required_specialists` fields
- Parse Orchestrator output strictly — fail loudly on malformed JSON
- Specialists can write response in natural language; structured data extracted separately
- Celery group pattern:
  ```python
  from celery import group
  job = group(
      strategic_analyze.s(context),
      finance_analyze.s(context),
  )()
  results = job.get(timeout=60)
  ```
- Keep specialist tasks idempotent and retryable
- Use `celery.result.GroupResult.get()` carefully — blocks the caller
