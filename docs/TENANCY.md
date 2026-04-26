# Multi-Tenancy

Sentinex uses schema-per-tenant isolation via `django-tenants`. This document describes the setup, conventions, and gotchas.

## Why Schema Per Tenant

- **Strong isolation**: each tenant has its own Postgres schema
- **Simpler GDPR**: `DROP SCHEMA <tenant>` cleanly removes all tenant data
- **Per-tenant backups**: dump/restore individual schemas
- **Reduced risk of cross-tenant data leaks**: impossible to accidentally query other tenant's data
- **Cleaner queries**: no `tenant_id` filter on every query

Trade-offs:
- More complex migrations (must run per schema)
- Higher connection overhead (schema switching)
- Limited to ~500 tenants on single Postgres instance (we're far below this)

## Setup

Django settings in `config/settings/base.py`:

```python
INSTALLED_APPS = [
    "django_tenants",

    # Shared apps (public schema)
    "apps.core",
    "apps.auth",
    "apps.billing",

    # Tenant apps (tenant schemas)
    "apps.agents",
    "apps.data_access",
    "apps.addons.weekly_brief",
]

SHARED_APPS = [
    "django_tenants",
    "apps.core",
    "apps.auth",
    "apps.billing",
    "django.contrib.auth",
    "django.contrib.contenttypes",
]

TENANT_APPS = [
    "apps.agents",
    "apps.data_access",
    "apps.addons.weekly_brief",
]

TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    # ... other middleware
]
```

## Tenant Model

```python
# apps/core/models.py

from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Subscription info
    plan = models.CharField(max_length=50, default="trial")
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # Auto-create schema when tenant is created
    auto_create_schema = True
    auto_drop_schema = True  # For development; use caution in production

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass
```

## Shared vs Tenant Models

### Shared Models (public schema)

Lives across all tenants:
- `User`, `Tenant`, `Domain`
- `Subscription`, `Invoice`, `Payment`
- `AddonRegistry`, `AddonActivation`
- `AuditLog` (cross-tenant audit)
- `LLMUsage` (cross-tenant usage for billing)

Located in:
- `apps/core/models.py`
- `apps/auth/models.py`
- `apps/billing/models.py`

### Tenant Models (tenant schemas)

Per-tenant data:
- `Organization` (one per tenant, represents the company)
- `DataSnapshot` (synced metrics)
- `Conversation` (agent history)
- `Report` (generated reports)
- Addon-specific models (weekly_brief config, etc.)

Located in:
- `apps/agents/models.py`
- `apps/data_access/models.py`
- `apps/addons/*/models.py`

## Migrations

### Running Migrations

```bash
# Migrate shared schema (for all SHARED_APPS)
poetry run python manage.py migrate_schemas --shared

# Migrate all tenant schemas (for all TENANT_APPS)
poetry run python manage.py migrate_schemas

# Migrate a specific tenant
poetry run python manage.py migrate_schemas --schema=<tenant_schema>

# Create migration for tenant app
poetry run python manage.py makemigrations <app_name>
```

### Migration Rules

1. **Shared migrations run first**, then tenant migrations
2. **Tenant migrations run once per tenant** — be mindful of performance with many tenants
3. **Migrations must be backward-compatible** during zero-downtime deploys:
   - Add column: non-nullable without default → NO (blocks old code)
   - Add column: nullable or with default → YES
   - Drop column: two-step (stop using, then drop) → YES
   - Rename column: two-step (add new, migrate data, drop old) → YES

## Tenant Resolution

### HTTP Requests

Middleware resolves tenant from subdomain:

```
Request: https://acme.sentinex.<tld>/dashboard/
Middleware extracts subdomain: "acme"
Looks up Domain with domain="acme.sentinex.<tld>"
Sets request.tenant = <Tenant acme>
Switches database connection to schema="acme"
```

### Celery Tasks

Celery tasks must manually set tenant context:

```python
from django_tenants.utils import schema_context

@shared_task
def generate_weekly_brief(tenant_schema: str, org_id: int):
    with schema_context(tenant_schema):
        org = Organization.objects.get(pk=org_id)
        # ... do work in tenant context
```

Always pass `tenant_schema` (not Tenant object) to tasks to avoid serialization issues.

### Management Commands

Use `tenant_command` prefix:

```bash
poetry run python manage.py tenant_command shell --schema=acme
poetry run python manage.py tenant_command loaddata fixtures.json --schema=acme
```

## Creating a Tenant

### Programmatically

```python
from apps.core.models import Tenant, Domain

tenant = Tenant.objects.create(
    schema_name="acme",
    name="ACME Corp",
)

Domain.objects.create(
    tenant=tenant,
    domain="acme.sentinex.<tld>",
    is_primary=True,
)

# Schema is auto-created; now run migrations if needed
from django.core.management import call_command
call_command("migrate_schemas", schema=tenant.schema_name)
```

### Via Management Command

```bash
poetry run python manage.py create_tenant
# Prompts for name, schema_name, domain
```

## Tenant Isolation Tests

Every test file that touches tenant data must verify isolation:

```python
import pytest
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

@pytest.mark.django_db
class TestTenantIsolation:
    def test_organizations_isolated(self):
        # Create tenant A with an organization
        tenant_a = Tenant.objects.create(schema_name="a", name="A")
        with schema_context("a"):
            Organization.objects.create(name="Org A")

        # Create tenant B with an organization
        tenant_b = Tenant.objects.create(schema_name="b", name="B")
        with schema_context("b"):
            Organization.objects.create(name="Org B")

        # Verify tenant A cannot see tenant B's organization
        with schema_context("a"):
            orgs = list(Organization.objects.all())
            assert len(orgs) == 1
            assert orgs[0].name == "Org A"
```

## Common Gotchas

### Foreign Keys Across Schemas

Tenant models CAN reference shared models (e.g., `User`). This works because the FK resolves in the shared schema.

Tenant models CANNOT reference each other across tenants. A tenant's data is isolated to its own schema.

### Settings and Constants

Cross-tenant constants (feature flags, config) live in the shared schema or settings.

Per-tenant constants live in tenant models (e.g., `Organization.settings` JSONField).

### Admin Interface

Django admin shows the active tenant's data. To access all tenants, superuser must switch schemas:

```bash
poetry run python manage.py tenant_command shell --schema=public
# Now can access Tenant, User across all tenants
```

### Signals

Signals fire within the active schema context. Be careful:

```python
@receiver(post_save, sender=Organization)
def on_org_created(sender, instance, created, **kwargs):
    if created:
        # Runs in current tenant schema
        # DO NOT try to write to another tenant's schema here
        pass
```

## Performance

### Connection Pooling

Schema switching has overhead. Use pgbouncer if connection count becomes an issue (typically 100+ tenants).

### Cached Querysets

Cache keys must include tenant:

```python
def get_cache_key(org, key):
    return f"tenant:{connection.schema_name}:{key}"
```

### Bulk Operations

For cross-tenant operations (billing, reporting), iterate through tenants:

```python
for tenant in Tenant.objects.filter(is_active=True):
    with schema_context(tenant.schema_name):
        # Do per-tenant work
        pass
```

## Backup Strategy

### Per-tenant Backup

```bash
pg_dump -n <schema_name> -f /backups/<tenant>_<date>.sql mydb
```

### Full Backup

```bash
pg_dump mydb -f /backups/full_<date>.sql
```

### GDPR Data Export

```bash
poetry run python manage.py export_tenant_data --schema=<tenant> --format=json --output=/tmp/
```

Generates all tenant data in structured format for GDPR Article 20 (data portability).

### GDPR Data Deletion

```bash
poetry run python manage.py delete_tenant --schema=<tenant> --confirm
```

This:
1. Exports data to archive
2. Drops schema (tenant data gone)
3. Soft-deletes Tenant record (keeps audit trail)
4. Removes user associations

## Planning for Scale

Current target: 10–50 tenants on single Postgres instance.

Scale path:
- 50–200 tenants: monitor connection pool, consider pgbouncer
- 200–500 tenants: consider Postgres replication (read replicas)
- 500+ tenants: consider sharding (split tenants across Postgres clusters)

Not a concern until we're well past MVP.
