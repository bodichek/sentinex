# Architecture

This document describes the full architecture of Sentinex across all layers.

## Design Principles

1. **Boring technology**: Django monolith, Postgres, Redis, Celery. No exotic stacks.
2. **AIOS-first**: Agentic architecture from day 1, even with narrow MVP scope.
3. **Addon-friendly**: Core is stable. Addons are modular. Adding new addon should not require core changes.
4. **Multi-tenant by design**: Schema per tenant, full data isolation.
5. **EU data sovereignty**: Deployable on EU infrastructure (Hetzner primary).
6. **Framework-agnostic**: No hard dependencies on Scaling Up / EOS / OKR brands.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│   VRSTVA 1: CLIENT LAYER          Browser, mobile           │
│   VRSTVA 2: EDGE LAYER            Nginx, SSL, rate limit    │
│   VRSTVA 3: FRONTEND LAYER        Tailwind + HTMX           │
│   VRSTVA 4: CORE LAYER            Platform, auth, billing   │
│   VRSTVA 5: AGENT LAYER           Orchestrator, specialists │
│   VRSTVA 6: DATA ACCESS LAYER     Insight Functions, MCP    │
│   VRSTVA 7: ADDONS LAYER          CEO Weekly Brief, ...     │
│   VRSTVA 8: PERSISTENCE LAYER     Postgres, Redis, S3       │
│   VRSTVA 9: ASYNC LAYER           Celery workers, beat      │
│   VRSTVA 10: INTEGRATION LAYER    MCP servers, LLM APIs     │
└─────────────────────────────────────────────────────────────┘
```

## Layer Details

### Layer 1: Client Layer

- Browser (primary): responsive web interface
- Mobile: responsive web, no native app in MVP
- Email digests: weekly briefs delivered to CEO inbox

### Layer 2: Edge Layer

- Nginx reverse proxy
- SSL termination (Let's Encrypt wildcard certificate)
- Subdomain routing (`<tenant>.sentinex.<tld>`)
- Rate limiting per tenant and per IP
- Static file serving
- Compression (gzip, brotli)

### Layer 3: Frontend Layer

- Django templates (server-rendered)
- Tailwind CSS for styling
- HTMX for partial updates and reactivity
- Alpine.js for light client-side interactivity
- No React / Vue / other SPA frameworks
- Multi-language support: Czech (primary), English (secondary)

### Layer 4: Core Layer

Core is the platform foundation. It includes:

**Tenancy**
- django-tenants with schema-per-tenant isolation
- Public schema for shared models (users, billing, audit logs, addon registry)
- Tenant schemas for per-tenant data (organizations, datasets, conversations, reports)

**Authentication**
- Django allauth (email + password)
- OAuth2 for API access
- Role-based permissions: Owner, Admin, Member, Viewer
- Session management

**User management**
- Invitation flow
- Profile management
- Role assignment per tenant
- Activity tracking

**Billing**
- Manual invoicing in MVP
- Usage tracking (LLM tokens, storage, API calls)
- Addon activation tracking

**API layer**
- REST API via Django REST Framework
- Versioning: `/api/v1/`, `/api/v2/`
- Token authentication for addons and external consumers
- OpenAPI schema auto-generated

**Addon registry**
- Discovery via `INSTALLED_APPS` scan
- Activation per tenant (feature flags)
- Configuration schema per addon

**Event bus**
- Django signals for synchronous in-process events
- Celery tasks for async cross-process events
- Pub/sub pattern for addon communication

**Audit & compliance**
- Audit log for all user actions
- LLM call audit log
- GDPR export/delete capability (basic in MVP, full later)
- Retention policies per data type

### Layer 5: Agent Layer

The intelligent core. Handles all AI interactions.

**Orchestrator**
- Entry point for user queries and scheduled agent tasks
- Classifies intent, determines needed specialists
- Parallelizes specialist invocations via Celery
- Composes final structured output
- Default model: Claude Sonnet

**Specialist agents**
- Strategic (high-level business analysis)
- Finance (financial signals and projections)
- People (team health, organizational signals)
- Customer (pipeline, deal risk, customer health)
- Addon-provided specialists (addon can register its own specialist)

**Memory system**
- Short-term: current conversation (Redis-backed)
- Medium-term: last 30 days of interactions (Postgres)
- Long-term: RAG index over company documents (pgvector)

**Guardrails**
- Pre-call: cost budget, scope validation, PII masking, prompt injection detection
- Post-call: output validation, PII unmasking for authorized users, compliance logging

**Context Builder**
- Gathers relevant Insight Function outputs
- Fetches memory (all layers)
- Constructs optimized prompt
- Token budgeting
- Caches by prompt hash

**LLM Gateway**
- Thin wrapper over Anthropic SDK
- Multi-model routing: Claude Sonnet (default), Claude Haiku (fallback)
- Token counting per tenant
- Retry logic with exponential backoff
- Redis caching (exact-match, hash of prompt)

### Layer 6: Data Access Layer

**This is the moat.** Business logic and methodology encoded as Python functions.

**Insight Functions**

Pure Python functions with typed inputs and outputs. Framework-agnostic (no Scaling Up / EOS / OKR branding). Examples:

- `get_weekly_metrics(org) -> WeeklyMetrics`
- `get_recent_anomalies(org) -> list[Anomaly]`
- `get_team_activity_summary(org, period) -> TeamActivity`
- `get_upcoming_commitments(org) -> list[Commitment]`
- `get_cashflow_snapshot(org) -> CashflowSnapshot`

Each function:
- Has typed inputs and outputs (Pydantic or dataclasses)
- Is unit tested with mock data
- Is cached in Redis where appropriate
- Is callable from agents, addons, and core

**MCP Gateway**

Abstraction over MCP servers.

- Self-hosted MCP servers for shared integrations (Google Workspace primary in MVP)
- Per-tenant credential storage (encrypted with django-cryptography)
- OAuth flow management
- Audit log for all MCP calls
- Token counting contribution to LLM cost tracking

**Direct API Clients**

Custom Python clients for systems without MCP servers.

- Future: Pohoda, ABRA, Helios (Czech accounting systems)
- Banking APIs (PSD2)
- Legacy ERP integrations

**Sync Pipelines**

Celery workers for ETL.

- Scheduled tasks (daily, hourly, weekly)
- Fetch from source → transform → store as metrics
- Emit events (`data.synced`) for downstream processing
- Data minimization: store metrics, not raw data
- Retention policy per data type

### Layer 7: Addons Layer

Django apps that implement specific functionality.

**Core addon in MVP: CEO Weekly Brief**

Each Monday at 07:00 (tenant time), generates a structured brief:
- Key metrics (from Insight Functions)
- Recent anomalies
- Team activity summary
- Upcoming commitments
- Cashflow snapshot

Delivered as:
- Email (HTML + plain text)
- Web dashboard view
- PDF export

**Future addons** (post-MVP):
- Quarterly Planning Cockpit
- Power of One Simulator
- Cash Flow Dashboard
- Culture Pulse (EU AI Act-safe, opt-in only)
- Strategic Risk Monitor
- Custom addons per client

**Addon contract**

- Addon is a Django app in `apps/addons/<name>/`
- Must have `manifest.py` with metadata
- Communicates with core only via REST API or event bus
- Never accesses core DB directly
- Has feature flag per tenant

### Layer 8: Persistence Layer

**PostgreSQL 16+**

Single database, schema per tenant (django-tenants).

Public schema (shared):
- users, tenants, billing
- addon_registry
- audit_log
- llm_usage

Tenant schemas (per tenant):
- organizations
- datasets (synced metrics)
- conversations (agent history)
- reports
- events

Extensions:
- pgvector (embeddings for RAG)
- pg_stat_statements (monitoring)
- btree_gin (JSON indexing)

**Redis**

- Session storage
- Celery broker
- Cache layer (Insight Function results, LLM responses)
- Rate limiting counters
- Pub/sub for real-time updates

**Object Storage**

- Hetzner Storage Box (S3-compatible) for files, reports, uploads
- Not in MVP; added when needed

### Layer 9: Async Layer

**Celery workers**

Different worker types for different workloads:
- LLM workers (high-memory for Anthropic calls)
- ETL workers (CPU-bound for data transformation)
- Notification workers (I/O-bound for emails)
- Report workers (mixed, PDF generation)

**Celery Beat**

Scheduled tasks:
- Weekly brief generation (Monday 07:00 per tenant timezone)
- Hourly data sync
- Daily cleanup tasks

**Task monitoring**
- Sentry for errors
- Hetzner monitoring for server resources
- Custom admin dashboard for queue health

### Layer 10: Integration Layer

**LLM Providers**

- Primary: Anthropic Claude Sonnet (via API)
- Fallback: Anthropic Claude Haiku (cheaper, simpler tasks)
- No GPT in MVP
- No self-hosted models in MVP

**Embeddings**

- OpenAI text-embedding-3-small
- Stored in pgvector

**MCP Servers**

- Google Workspace (official Anthropic MCP server)
- Future: Microsoft 365, Slack, HubSpot, Jira, Notion, GitHub

**External services**

- Sentry (error tracking)
- Hetzner monitoring (infrastructure)

## Request Flow Example

User query: "How is Q1 going?"

```
Browser
  ↓ HTTPS
Nginx (SSL, rate limit, tenant routing)
  ↓
Django (auth check, tenant context)
  ↓
Agent Layer — Orchestrator
  ↓
  Classify: strategic query
  ↓
  Plan: call 3 specialists in parallel
  ↓
Guardrails (pre-check: cost budget, scope)
  ↓
Context Builder
  ↓
  Fetch memory, identify needed Insight Functions
  ↓
Specialists (parallel via Celery)
  ↓           ↓            ↓
Strategic   Finance      People
  ↓           ↓            ↓
Data Access Layer
  ↓           ↓            ↓
get_q1_rocks  get_cash    get_team_health
  ↓           ↓            ↓
Postgres (synced metrics)
  ↓
Each specialist interprets its data via LLM
  ↓
Orchestrator composes final response
  ↓
Guardrails (post-check: output validation, audit log)
  ↓
Frontend rendering
```

Total: 5–20 seconds. Tokens: ~10–20K. Cost: ~10–20 CZK per complex query.

## Technology Decisions Rationale

**Why Django monolith over microservices?**
- Single developer, rapid iteration required
- Shared code base reduces cognitive load
- Easier debugging
- Can be decomposed later if needed

**Why schema-per-tenant over tenant_id column?**
- Better data isolation (defense in depth)
- Easier GDPR compliance (DROP SCHEMA = done)
- Simpler backups per tenant
- Standard Django pattern with django-tenants

**Why Redis for cache and broker?**
- Single infrastructure dependency
- Mature Python client
- Handles all async use cases

**Why HTMX over React?**
- Faster development (server-rendered)
- Fewer moving parts
- Easier debugging
- Addons can contribute templates naturally

**Why Celery?**
- Standard Django async solution
- Mature, well-documented
- Handles LLM calls, ETL, scheduled tasks in one framework

## Non-Goals

- Real-time collaborative editing
- Mobile-native apps
- On-device LLM inference
- Blockchain, crypto, Web3
- Voice interfaces (post-MVP if ever)
- Video generation (post-MVP if ever)

## Scaling Considerations

**Current capacity target**: 10–20 tenants on single Hetzner server.

**Scaling path**:
- 20–50 tenants: upgrade to larger single server
- 50–100 tenants: separate DB server, multiple app servers behind load balancer
- 100+ tenants: consider read replicas, dedicated Celery pool
- 200+ tenants: consider Kubernetes migration (not before)

**Key bottlenecks to watch**:
- LLM API rate limits (handle with queuing)
- Postgres connection pool (use pgbouncer when needed)
- Redis memory (monitor and scale vertical first)
