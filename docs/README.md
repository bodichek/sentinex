# Sentinex Documentation Index

Curated entry points by what you're trying to do.

## Architecture & design

- [ARCHITECTURE.md](ARCHITECTURE.md) — full layered architecture, technology
  decisions, request flow, scaling considerations.
- [TENANCY.md](TENANCY.md) — django-tenants model, schema-per-tenant
  isolation rules, tenant resolution.
- [SECURITY.md](SECURITY.md) — auth model, encryption at rest, audit
  logging, GDPR posture.

## Building things

- [DATA_ACCESS.md](DATA_ACCESS.md) — Insight Functions, MCP Gateway, sync
  pipelines, **Knowledge Pipeline (RAG)** over Workspace.
- [AGENTS.md](AGENTS.md) — Orchestrator + specialist pattern, prompt
  files, memory tiers, guardrails. Includes the Knowledge specialist.
- [ADDONS.md](ADDONS.md) — addon contract, manifest, isolation rules,
  Weekly Brief reference implementation.

## Connecting external systems

- [GOOGLE_WORKSPACE_DWD.md](GOOGLE_WORKSPACE_DWD.md) — **Service Account +
  Domain-Wide Delegation** company-wide read connector. Full setup
  (Google side + Sentinex side), scopes, RAG ingestion pipeline, cost
  model, GDPR notes.

## Operating

- [DEPLOYMENT.md](DEPLOYMENT.md) — Hetzner production setup, zero-downtime
  deploys, env variables (incl. Workspace DWD), Celery Beat schedule.
- [DEVELOPMENT.md](DEVELOPMENT.md) — local setup, daily workflow, code
  style, debugging, **stub mode for offline RAG dev**.
- [TESTING.md](TESTING.md) — test categories, fixtures, mocking patterns.
- [ONBOARDING.md](ONBOARDING.md) — pilot customer onboarding playbook.

## Cross-references

- New developer? Start with `ARCHITECTURE.md` → `DEVELOPMENT.md`, then
  pick the layer you'll work on (`AGENTS.md` or `DATA_ACCESS.md`).
- Connecting a customer's Workspace? Start with
  `GOOGLE_WORKSPACE_DWD.md` end-to-end.
- Shipping to production? `DEPLOYMENT.md` + the env-vars section.
