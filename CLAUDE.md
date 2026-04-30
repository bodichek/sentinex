# CLAUDE.md — Rules for Claude Code

This file provides guidance to Claude Code when working on the Sentinex project.

## Project Overview

Sentinex is an AI Operating System for mid-market companies. Multi-tenant Django platform with agentic AI, modular addons, and EU-sovereign deployment.

Primary goals:
- Build a production-grade AIOS from day 1
- Keep architecture clean and addon-friendly
- Prioritize velocity during MVP phase
- Every decision favors iteration speed over premature optimization

## Technology Stack (non-negotiable)

- Python 3.12
- Django 5.1 + DRF
- PostgreSQL 16 + pgvector
- Redis 7
- Celery + Celery Beat
- Poetry for dependency management
- Ruff for linting/formatting
- mypy strict mode
- pytest + pytest-django
- django-tenants (schema per tenant)
- Anthropic SDK (Claude Sonnet + Haiku)
- OpenAI SDK (embeddings only)
- Tailwind CSS + HTMX + Alpine.js

Do NOT introduce alternative frameworks without explicit request (e.g., FastAPI, React, Next.js, LangChain, LangGraph).

## Project Structure

```
sentinex/
├── apps/
│   ├── core/           # Core platform
│   ├── agents/         # Agent Layer
│   ├── data_access/    # Insight Functions, MCP Gateway
│   └── addons/         # Addon modules
│       └── weekly_brief/
├── config/             # Django settings (dev, prod, test)
├── docs/               # Project documentation
├── .claude/            # Skills and prompts
├── prompts/            # Development prompts
└── tests/              # Integration tests
```

## Core Architectural Rules

### 1. Addon isolation

- Addons NEVER access core database tables directly
- Addons communicate with core only via REST API or event bus (Django signals + Celery tasks)
- Each addon is a self-contained Django app with its own migrations, models, views, templates
- Core has no knowledge of specific addons — only the addon registry interface

### 2. Data Access Layer is the moat

- All AI-consumable business logic lives in `apps/data_access/insight_functions/`
- Insight Functions are pure Python functions with typed inputs and outputs
- Functions are framework-agnostic (no Scaling Up / EOS / OKR branding in function names)
- Each function has unit tests with mock data

### 3. Multi-tenancy is sacred

- Every model must live in either the shared schema or tenant schema, never both
- Cross-tenant queries are forbidden outside of admin tooling
- Tenant resolution happens at middleware level, never in views
- Tests MUST verify tenant isolation

### 4. LLM calls are expensive and asynchronous

- Never call LLM synchronously in a view handler
- All LLM calls go through `apps/agents/llm_gateway.py`
- Gateway handles: model routing, token counting, caching (Redis exact-match), retries
- Use Celery tasks for anything that triggers an LLM call

### 5. Guardrails are not optional

- Every agent invocation MUST pass through pre-call guardrails (cost budget, scope check, PII masking)
- Every agent response MUST pass through post-call guardrails (output validation, audit log)
- Bypassing guardrails requires explicit comment explaining why

## Code Style

- Ruff for linting and formatting (configured in `pyproject.toml`)
- Line length: 100
- Docstrings: Google style
- Type hints: mandatory on all public functions and class methods
- mypy: strict mode
- Imports: absolute only (`from apps.core.models import Organization`, never relative)

## Testing Requirements

- pytest + pytest-django
- Tests live in `tests/` at repo root for integration tests, and `tests/` subdirectory within each app for unit tests
- Minimum coverage target: 70% (not enforced in MVP, but aim for it)
- Every Insight Function has at least one unit test
- Every addon has at least one integration test
- Tenant isolation has dedicated tests

## Commit Style

- Conventional commits required:
  - `feat:` new feature
  - `fix:` bug fix
  - `docs:` documentation
  - `refactor:` code refactoring
  - `test:` adding tests
  - `chore:` tooling, dependencies
  - `perf:` performance improvement

- **IMPORTANT**: Do NOT include `Co-authored-by: Claude` or similar attribution in commit messages.
- Keep commit messages concise but descriptive.
- One logical change per commit when possible.

## Documentation Maintenance

**MANDATORY:** Every commit MUST update the relevant doc in `docs/` in the
same commit as the code change. Reviewers should reject any code-only PR
that touches public APIs, agents, data-access, connectors, deployment or
architecture without a corresponding doc update. "I'll add docs later" is
not acceptable.

The following files must stay synchronized with code:

- `docs/ARCHITECTURE.md` — when architecture changes
- `docs/ADDONS.md` — when addon contract changes
- `docs/AGENTS.md` — when agent layer changes (specialists, guardrails, gateway)
- `docs/DATA_ACCESS.md` — when Insight Functions API or models change
- `docs/CONNECTORS.md` — when a connector is added/changed (auth, scopes, sync, tools, env vars)
- `docs/SECURITY.md` — when auth, encryption, decorators or threat model changes
- `docs/DEPLOYMENT.md` — when deployment process changes
- Provider-specific docs (e.g. `docs/GOOGLE_WORKSPACE_DWD.md`) when their connector changes

Checklist before every commit:
1. Did I add/change a connector? → update `docs/CONNECTORS.md`.
2. Did I add/change an Insight Function? → update `docs/DATA_ACCESS.md` and the registry in `apps/data_access/insight_functions/__init__.py`.
3. Did I add a new env var? → update `.env.example` AND the relevant doc.
4. Did I change a security-relevant primitive (decorator, key handling, masking)? → update `docs/SECURITY.md`.
5. Did I add a Celery beat task? → mention it in the relevant doc with cadence + purpose.

Auto-documentation workflow is set up in `.github/workflows/docs-auto.yml` — it runs after push to `main` and opens a PR with doc updates if needed. The auto-PR is a safety net, not a substitute for documenting in the original commit.

## Security Rules

- Never commit secrets. Use `.env` locally, environment variables on the server.
- Never log sensitive data (emails content, financial data, PII).
- All external API credentials stored with django-cryptography field-level encryption.
- OAuth tokens refreshed automatically, with 5-minute buffer before expiration.

## Deployment

- Development: local Docker Compose
- Production: Hetzner Cloud with Docker Compose + Nginx zero-downtime reload
- Zero-downtime strategy: two app container instances, Nginx upstream switch
- CI/CD: GitHub Actions (`.github/workflows/`)
- Sentry for error tracking
- Hetzner monitoring for infrastructure metrics

## When In Doubt

- Read the relevant doc in `docs/` first
- If the doc doesn't cover it, check the relevant skill in `.claude/skills/`
- If still unclear, ask the user before making architectural decisions
- Prefer simple solutions over clever ones
- Favor explicit over implicit
- Small, reviewable changes over large refactors

## What Not to Do

- Do not add new dependencies without justification
- Do not introduce microservices, GraphQL, or async Django without discussion
- Do not bypass the Agent Layer for LLM calls
- Do not write addons that depend on other addons directly (use events)
- Do not include Claude Code attribution in commits
- Do not optimize prematurely — MVP first, optimize when needed
- Do not write custom ORM layers, auth systems, or reinvent Django built-ins

## Primary Language

- Code and comments: English
- Documentation files (`docs/`): English
- Commit messages: English
- Internal notes and TODO comments: English preferred, Czech acceptable
- User-facing UI: Czech (initially), English later
