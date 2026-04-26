# Sentinex

AI Operating System for mid-market CEOs. EU-sovereign, framework-agnostic, multi-tenant.

## What is Sentinex

Sentinex is an agentic AI platform designed as the strategic nervous system for mid-market companies (30–200 employees). It provides structured reporting, decision support, quarterly planning, and organizational health monitoring — delivered as a multi-tenant SaaS with addon modules.

The initial MVP focuses on **CEO Weekly Brief** — a structured Monday morning report aggregating key metrics, anomalies, and upcoming commitments from connected company systems.

## Quick Start

### Prerequisites

- Python 3.12
- Poetry
- PostgreSQL 16+ with pgvector
- Redis 7+
- Docker and Docker Compose

### Local Development

```bash
# Clone the repo
git clone git@github.com:<owner>/sentinex.git
cd sentinex

# Install dependencies
poetry install

# Copy env template
cp .env.example .env
# Fill in required values (see docs/DEVELOPMENT.md)

# Start services
docker-compose up -d postgres redis

# Run migrations
poetry run python manage.py migrate_schemas --shared
poetry run python manage.py migrate_schemas

# Create superuser and first tenant
poetry run python manage.py createsuperuser
poetry run python manage.py create_tenant

# Run dev server
poetry run python manage.py runserver
```

Visit `http://localhost:8000` and access a tenant via subdomain (configure `/etc/hosts`).

### Full setup guide

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Architecture Overview

```
┌────────────────────────────────────────┐
│  Frontend (Tailwind + HTMX)            │
├────────────────────────────────────────┤
│  Core (Django 5.1 + DRF)               │
│  - Tenancy (schema per tenant)         │
│  - Auth, billing, API, event bus       │
├────────────────────────────────────────┤
│  Agent Layer                           │
│  - Orchestrator + Specialists          │
│  - Memory, guardrails                  │
├────────────────────────────────────────┤
│  Data Access Layer                     │
│  - Insight Functions (your moat)       │
│  - MCP Gateway (Google Workspace, ...) │
│  - Direct API Clients                  │
├────────────────────────────────────────┤
│  Addons (CEO Weekly Brief, ...)        │
├────────────────────────────────────────┤
│  Persistence (Postgres + pgvector,     │
│  Redis, Object Storage)                │
├────────────────────────────────────────┤
│  Async (Celery workers + beat)         │
└────────────────────────────────────────┘
```

For full architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project Structure

```
sentinex/
├── apps/
│   ├── core/           # Core platform (auth, tenancy, billing)
│   ├── agents/         # Agent Layer
│   ├── data_access/    # Insight Functions, MCP Gateway
│   └── addons/         # Addon modules
│       └── weekly_brief/
├── config/             # Django settings
├── docs/               # Project documentation
├── .claude/            # Claude Code skills and prompts
├── prompts/            # Development prompts by step
└── tests/              # Integration tests
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Addon Development](docs/ADDONS.md)
- [Agent Layer](docs/AGENTS.md)
- [Data Access Layer](docs/DATA_ACCESS.md)
- [Multi-Tenancy](docs/TENANCY.md)
- [Testing](docs/TESTING.md)
- [Security](docs/SECURITY.md)

## Technology Stack

- **Backend**: Python 3.12, Django 5.1, Django REST Framework
- **Database**: PostgreSQL 16+ with pgvector extension
- **Cache / Broker**: Redis 7+
- **Multi-tenancy**: django-tenants (schema per tenant)
- **Async**: Celery + Celery Beat
- **Frontend**: Tailwind CSS + HTMX + Alpine.js
- **LLM**: Anthropic Claude Sonnet (primary) + Claude Haiku (fallback)
- **Embeddings**: OpenAI text-embedding-3-small
- **Package Manager**: Poetry
- **Code Quality**: Ruff, mypy strict, pytest
- **CI/CD**: GitHub Actions
- **Deployment**: Docker Compose, Nginx zero-downtime reload
- **Infrastructure**: Hetzner Cloud
- **Monitoring**: Sentry, Hetzner monitoring

## License

Proprietary. All rights reserved.
