# Prompt 08: Insight Functions

## Goal

Implement the first 5 Insight Functions that aggregate synced data into typed, agent-consumable outputs. These are the business logic core of Sentinex.

## Prerequisites

- Prompt 07 complete (Google Workspace syncing data)
- `DataSnapshot` model has real metrics

## Context

Insight Functions are Sentinex's moat. Business methodology encoded as typed, testable, cached Python functions. Framework-agnostic names (no Scaling Up branding). See `docs/DATA_ACCESS.md` and `.claude/skills/add-insight-function.md`.

## Constraints

- Pure functions: no side effects
- Typed inputs (Organization) and outputs (dataclass)
- Framework-agnostic naming
- Each function unit tested with mocked data
- Cache expensive computations in Redis

## Deliverables

1. `apps/data_access/insight_functions/` subpackage:
   - `__init__.py` — registers all functions in `INSIGHT_FUNCTIONS` dict
   - `types/` — output type definitions
     - `strategic.py`
     - `finance.py`
     - `people.py`
   - `strategic.py` — strategic functions
   - `finance.py` — finance functions
   - `people.py` — people functions
   - `exceptions.py` — `InsufficientData`, etc.
2. 5 Insight Functions implemented:
   - `get_weekly_metrics(org) -> WeeklyMetrics` — aggregated KPIs from all sources for past 7 days
   - `get_recent_anomalies(org, period_days=14) -> list[Anomaly]` — unusual patterns in data
   - `get_team_activity_summary(org, period_days=7) -> TeamActivity` — from Google Workspace calendar/email metadata
   - `get_upcoming_commitments(org, days_ahead=7) -> list[Commitment]` — from calendar events
   - `get_cashflow_snapshot(org) -> CashflowSnapshot` — basic version using manually entered KPIs (accounting integration later)
3. Caching infrastructure:
   - `apps/core/cache.py` with `@cache_result(ttl, key_prefix)` decorator
   - Tenant-aware cache key prefix
4. Manual KPI input (since no accounting integration yet):
   - Model `ManualKPI` (tenant schema): `name`, `value`, `unit`, `period_end`, `notes`
   - Admin UI for CEO to input KPIs (revenue, cash on hand, etc.)
   - Used by `get_cashflow_snapshot` and `get_weekly_metrics`
5. Specialist agents updated to use Insight Functions:
   - `StrategicSpecialist.get_insight_functions()` returns relevant function names
   - Context Builder fetches Insight Function outputs before LLM call
   - Prompt includes function outputs as structured context
6. Unit tests for all 5 functions:
   - Happy path with full data
   - `InsufficientData` raised when no data
   - Partial data handled gracefully
   - Cache hit returns same result without recomputing
   - Tenant isolation (function only sees tenant's own data)
7. Integration test: run `get_weekly_metrics` on a tenant with synced Google data, verify real numbers returned

## Acceptance Criteria

- Calling `get_weekly_metrics(org)` returns `WeeklyMetrics` with real data (not mock)
- Functions raise `InsufficientData` exception when data missing
- Results cached on second call (verify via Redis or logs)
- Strategic and Finance specialists now produce responses informed by Insight Functions
- User query "How's our cash position?" yields response citing actual manual KPIs
- Tests pass
- `mypy` strict passes

## Next Steps

After this prompt, Phase 2 is complete. Proceed to `phase-3-addon.md` → `09-addon-framework.md`.

## Notes for Claude Code

- Return types as dataclasses (or Pydantic if easier for serialization)
- Include `data_quality` field in outputs: "high", "partial", "missing"
- For `get_team_activity_summary`: use calendar events count, email thread count, unique correspondents — no content
- For `get_upcoming_commitments`: read calendar events with start time in next 7 days
- For `get_recent_anomalies`: simple z-score on time series (e.g., daily email count) to detect spikes/drops
- For `get_cashflow_snapshot`: requires manual KPI input in admin (revenue, cash, monthly expenses)
- Cache keys include tenant schema name (auto-included via connection context)
- Use function name as key_prefix: `cache_key = f"insight:{tenant_schema}:{func_name}:{args_hash}"`
- Cache TTL: 1 hour for most, 24 hours for stable ones (cashflow snapshot changes less often)
- Update specialist YAML prompts to instruct model: "You have access to these tools: [list]. Call them to gather data before answering."
