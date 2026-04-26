# Phase 1: Foundation (Week 1)

## Goal

Build the AIOS skeleton: Django multi-tenant platform with LLM Gateway, Agent Layer (Orchestrator + 2 specialists), and basic memory. By the end of this phase, you should be able to send a query through the system and receive an LLM-generated response, with full tenant isolation.

## Prerequisites

- Empty GitHub repo (`sentinex`)
- Hetzner account with access to create a server
- Anthropic API key (from Claude Max for development)
- OpenAI API key (for embeddings)
- `.env` file configured

## Reference Materials

Read these first if not already familiar:
- `CLAUDE.md` — rules for this project
- `docs/ARCHITECTURE.md` — layered architecture
- `docs/TENANCY.md` — multi-tenant setup
- `docs/AGENTS.md` — agent layer design
- `docs/DEVELOPMENT.md` — local setup

## Deliverables

By end of Phase 1:

1. **Functional Django project** with multi-tenancy
2. **Development environment** running locally via Docker Compose
3. **Deployed** to a Hetzner server (staging)
4. **Auth flow** working (email + password)
5. **Tenant creation** via management command
6. **LLM Gateway** with Claude Sonnet + Haiku routing
7. **Orchestrator** with intent classification
8. **2 specialist agents** (Strategic, Finance) — minimal implementation
9. **Memory system** — short-term (Redis) + medium-term (Postgres)
10. **Guardrails** — cost budget, PII masking, basic scope check
11. **Basic frontend** — login, dashboard, query input
12. **CI/CD** — GitHub Actions running tests on PR
13. **Tests** — tenant isolation, LLM gateway, orchestrator

## Constraints

- Use only technologies specified in CLAUDE.md
- No new dependencies without justification
- Keep scope minimal — functional > feature-rich
- Every commit follows conventional commits (no Claude attribution)
- All code passes ruff + mypy strict

## Step-by-Step Breakdown

### Step 1.1: Project Setup

Create the base Django project with Poetry, multi-tenant support, and local dev environment.

See: `prompts/01-project-setup.md`

### Step 1.2: Tenancy Layer

Configure django-tenants, create Tenant and Domain models, middleware, and first tenant.

See: `prompts/02-django-tenancy.md`

### Step 1.3: Authentication

Set up Django allauth with email + password, roles, sessions.

See: `prompts/03-auth-basic.md`

### Step 1.4: LLM Gateway

Build the thin wrapper over Anthropic SDK with multi-model routing.

See: `prompts/04-llm-gateway.md`

### Step 1.5: Agent Layer Core

Orchestrator + 2 specialists (Strategic, Finance). Basic implementation.

See: `prompts/05-agent-layer.md`

### Step 1.6: Memory and Guardrails

Short-term Redis memory, medium-term Postgres memory, basic guardrails.

See: `prompts/06-memory-guardrails.md`

## Acceptance Criteria

Phase 1 is complete when:

1. **Setup works**: `docker-compose up` then `poetry run python manage.py runserver` succeeds
2. **Auth works**: can register user, log in, log out
3. **Tenant works**: can create tenant, access via subdomain
4. **Query works**: authenticated user can submit query, Orchestrator routes to Specialist, LLM responds
5. **Isolation works**: tenant isolation tests pass
6. **CI passes**: GitHub Actions green on main
7. **Deploy works**: can push to main, code is on staging server
8. **Docs current**: all relevant docs reflect implemented reality

## What NOT to Do in Phase 1

- Don't build addons yet
- Don't connect to real data sources (Google Workspace, etc.)
- Don't optimize performance
- Don't add extra LLM providers (no GPT)
- Don't set up advanced monitoring beyond Sentry
- Don't write marketing copy or user-facing polish

## Verification

End of Phase 1 smoke test:

```bash
# 1. Clone and setup
git clone git@github.com:<owner>/sentinex.git
cd sentinex
poetry install
cp .env.example .env
# Edit .env

# 2. Start services
docker-compose up -d postgres redis

# 3. Setup DB
poetry run python manage.py setup_postgres
poetry run python manage.py migrate_schemas --shared
poetry run python manage.py migrate_schemas

# 4. Create tenant
poetry run python manage.py create_tenant  # Creates "demo" tenant

# 5. Create user
poetry run python manage.py createsuperuser

# 6. Run server
poetry run python manage.py runserver

# 7. Visit http://demo.sentinex.local:8000, log in, submit query
# Should receive LLM response via orchestrator + specialist
```

## Estimated Effort

- **Time**: 5 days working 8–16 hours each
- **Lines of code**: ~3000–5000 (excluding tests and configs)
- **Dependencies**: Django, django-tenants, DRF, anthropic, openai, celery, redis, postgres client

## Next Phase

Once Phase 1 is complete, move to:
- `.claude/prompts/phase-2-data-layer.md` — Connect to Google Workspace, build Insight Functions

## Questions to Ask Before Starting

- Is the Hetzner server provisioned?
- Is the `.env` fully configured?
- Is the database backup strategy decided (can skip for Phase 1)?
- Is the domain DNS configured (can use `*.sentinex.local` for dev)?

If any of these is "no", address before starting Phase 1 implementation.
