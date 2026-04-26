# Development Guide

## Prerequisites

- Python 3.12
- Poetry
- PostgreSQL 16+ with pgvector extension
- Redis 7+
- Docker and Docker Compose
- Git

## Initial Setup

### 1. Clone and install

```bash
git clone git@github.com:<owner>/sentinex.git
cd sentinex
poetry install
```

### 2. Environment configuration

```bash
cp .env.example .env
```

Fill in the required values in `.env`. See `.env.example` for documentation of each variable.

Required for development:
- `SECRET_KEY` — Django secret key (generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `ANTHROPIC_API_KEY` — get from https://console.anthropic.com
- `OPENAI_API_KEY` — for embeddings only
- `POSTGRES_*` — database credentials
- `REDIS_URL` — Redis connection string

### 3. Start services

**Linux / macOS (Docker):**
```bash
docker-compose up -d postgres redis
```

This starts PostgreSQL (with pgvector) and Redis.

**Windows without Docker (native):**

If Docker Desktop isn't available (e.g., VM without nested virtualization), install
Postgres and a Redis-compatible server natively:

```powershell
winget install -e --id PostgreSQL.PostgreSQL.16
winget install -e --id Memurai.MemuraiDeveloper
```

After install, create the `sentinex` role and databases (run in elevated PowerShell):

```powershell
$env:PGPASSWORD = "<postgres_superuser_password>"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -c `
  "CREATE USER sentinex WITH PASSWORD 'sentinex' SUPERUSER CREATEDB;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -c `
  "CREATE DATABASE sentinex OWNER sentinex;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -c `
  "CREATE DATABASE sentinex_test OWNER sentinex;"
```

> **pgvector note**: pgvector has no prebuilt Windows binary. It must be compiled
> with MSVC Build Tools, or you can skip it until you move to Linux/Docker.
> The `setup_postgres` command will skip the vector extension with a warning
> if it isn't installed. Vector-backed features (Phase 2+: long-term memory,
> RAG) require it — install on Linux server or compile locally when needed.

### 4. Database setup

```bash
# Create extensions (pgvector, etc.)
poetry run python manage.py setup_postgres

# Run shared schema migrations (for public schema)
poetry run python manage.py migrate_schemas --shared

# Run tenant migrations (for all tenant schemas)
poetry run python manage.py migrate_schemas
```

### 5. Create superuser

```bash
poetry run python manage.py createsuperuser
```

### 6. Create first tenant

```bash
poetry run python manage.py create_tenant
```

This interactive command creates a tenant (organization) and assigns a subdomain.

### 6b. Bootstrap public tenant

```bash
poetry run python manage.py bootstrap_public_tenant
```

This creates the `public` Tenant row and registers `sentinex.local` as its
primary domain. Required before any subdomain request can resolve.

### 7. Configure local subdomain access

Add to `/etc/hosts` (Linux/Mac) or `C:\Windows\System32\drivers\etc\hosts` (Windows):

```
127.0.0.1 sentinex.local
127.0.0.1 demo.sentinex.local
127.0.0.1 test.sentinex.local
```

### 8. Run development server

```bash
poetry run python manage.py runserver
```

Access:
- Public site: `http://sentinex.local:8000`
- Demo tenant: `http://demo.sentinex.local:8000`

## Development Workflow

### Branch naming

- `feat/<short-description>` — new features
- `fix/<short-description>` — bug fixes
- `refactor/<short-description>` — code refactoring
- `docs/<short-description>` — documentation only
- `chore/<short-description>` — tooling, deps

### Commit messages

Conventional Commits format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

Example:
```
feat(agents): add Finance specialist agent

Implements a specialist agent for financial signal analysis.
Uses Claude Sonnet for reasoning and connects to Insight Functions.
```

**Important**: Do NOT add `Co-authored-by: Claude` to commits.

### Running tests

```bash
# All tests
poetry run pytest

# Specific app
poetry run pytest apps/core/tests/

# With coverage
poetry run pytest --cov=apps --cov-report=html

# Watch mode (requires pytest-watch)
poetry run ptw
```

### Linting and formatting

```bash
# Check formatting
poetry run ruff check .

# Auto-fix
poetry run ruff check --fix .

# Format code
poetry run ruff format .

# Type checking
poetry run mypy .
```

### Database operations

```bash
# Create migration for tenant schemas
poetry run python manage.py makemigrations <app>

# Apply migrations
poetry run python manage.py migrate_schemas

# Reset development database (careful!)
docker-compose down -v
docker-compose up -d postgres redis
poetry run python manage.py setup_postgres
poetry run python manage.py migrate_schemas --shared
poetry run python manage.py migrate_schemas
```

### Celery workers

Development:
```bash
# Run worker
poetry run celery -A config worker --loglevel=info

# Run beat (scheduler)
poetry run celery -A config beat --loglevel=info

# Run both together with Honcho or similar
```

### Working with addons

See [ADDONS.md](ADDONS.md) for full addon development guide.

Quick commands:
```bash
# List installed addons
poetry run python manage.py list_addons

# Activate addon for tenant
poetry run python manage.py activate_addon --tenant demo --addon weekly_brief
```

## Code Style

### Python

- Line length: 100 characters
- Type hints: mandatory on public functions and class methods
- Docstrings: Google style
- Imports: absolute only

Example:
```python
from apps.core.models import Organization

def get_weekly_metrics(org: Organization) -> WeeklyMetrics:
    """Compute weekly metrics for an organization.

    Args:
        org: The organization to compute metrics for.

    Returns:
        WeeklyMetrics object with aggregated data.

    Raises:
        NoDataAvailable: If the organization has no data sources connected.
    """
    ...
```

### Django

- Use class-based views for anything non-trivial
- Keep business logic OUT of views; put it in services or Insight Functions
- Use Django forms for form handling (don't reinvent validation)
- Use `select_related` and `prefetch_related` for query optimization

### Templates

- Tailwind CSS utility classes
- HTMX for interactivity
- Alpine.js for light client-side state
- Never inline JavaScript longer than a few lines

## Debugging

### Django shell

```bash
poetry run python manage.py shell
```

Tenant-aware shell:
```bash
poetry run python manage.py tenant_command shell --schema=demo
```

### SQL query debugging

Enable in `config/settings/dev.py`:
```python
LOGGING['loggers']['django.db.backends'] = {
    'level': 'DEBUG',
    'handlers': ['console'],
}
```

### LLM debugging

All LLM calls go through `apps/agents/llm_gateway.py`. Check:
- Django admin → LLM Usage log
- Sentry (if configured)
- Logs at `INFO` level for `apps.agents.llm_gateway`

## Common Issues

### Tenant subdomain not working

- Check `/etc/hosts` entries
- Check `TENANT_HOST` in `.env`
- Check django-tenants configuration in settings

### pgvector extension missing

```bash
poetry run python manage.py setup_postgres
```

Or manually:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Celery tasks not running

- Check Redis is running: `redis-cli ping`
- Check worker logs
- Check task is registered: `poetry run celery -A config inspect registered`

## Daily Development Routine

Recommended structure for focused work:

1. **Morning standup (self)**: review yesterday's progress, plan today's 3 priorities
2. **Deep work blocks**: 90–120 min focused on one task, no notifications
3. **Commits frequently**: small, atomic commits; push to branch
4. **Evening review**: what went well, what's blocked, update sprint board

## Sprint and Review Cadence

- **Daily**: personal standup (5 min, written note)
- **Weekly**: Friday afternoon retrospective (30 min)
- **Milestone**: every 2 weeks, review against 30-day plan
