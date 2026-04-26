# Skill: Debug Multi-Tenant Issues

Use this skill when debugging issues specific to multi-tenancy.

## When to Use

- Data appears in wrong tenant
- "Tenant not found" errors
- Migrations run on some tenants but not others
- Cross-tenant data leak suspected
- Celery task fails because tenant context missing

## Diagnostic Commands

### List all tenants

```bash
poetry run python manage.py list_tenants
```

Or in shell:
```python
from apps.core.models import Tenant
for t in Tenant.objects.all():
    print(f"{t.schema_name}: {t.name} - active={t.is_active}")
```

### Check tenant schema exists in DB

```sql
-- In psql
\dn   -- list all schemas
```

Or Django:
```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT schema_name FROM information_schema.schemata;")
    for row in cursor.fetchall():
        print(row[0])
```

### Check current schema

```python
from django.db import connection
print(connection.schema_name)
```

### Switch to tenant context

```python
from django_tenants.utils import schema_context

with schema_context("tenant_schema_name"):
    # Queries here run in tenant_schema_name context
    orgs = Organization.objects.all()
```

### Run shell in tenant context

```bash
poetry run python manage.py tenant_command shell --schema=<tenant_name>
```

## Common Issues and Fixes

### Issue: "Tenant not found for domain X"

Cause: No `Domain` object for the requested subdomain.

Check:
```python
from apps.core.models import Domain
Domain.objects.filter(domain="acme.sentinex.local").exists()
```

Fix: Create domain record.
```python
from apps.core.models import Tenant, Domain
tenant = Tenant.objects.get(schema_name="acme")
Domain.objects.create(
    tenant=tenant,
    domain="acme.sentinex.local",
    is_primary=True,
)
```

### Issue: Data visible in wrong tenant

Cause: Query ran in wrong schema context, or cross-schema data leak.

Check:
1. Is the model in `SHARED_APPS` when it should be in `TENANT_APPS`?
2. Are you using `schema_context()` correctly?
3. Did middleware correctly set the tenant?

Debug:
```python
# In view
print(f"Request tenant: {request.tenant}")
print(f"Connection schema: {connection.schema_name}")
```

Fix: Ensure model is in correct app and correct context used.

### Issue: Migrations applied to some tenants, not others

Cause: `migrate_schemas` was interrupted or skipped some tenants.

Check:
```bash
poetry run python manage.py showmigrations --schema=<tenant_name>
```

Fix: Run migration for specific tenant.
```bash
poetry run python manage.py migrate_schemas --schema=<tenant_name>
```

### Issue: Celery task fails with "tenant not found"

Cause: Celery task didn't set tenant context.

Bad:
```python
@shared_task
def do_something(org_id):
    org = Organization.objects.get(pk=org_id)  # Fails — no tenant context
```

Good:
```python
from django_tenants.utils import schema_context

@shared_task
def do_something(tenant_schema, org_id):
    with schema_context(tenant_schema):
        org = Organization.objects.get(pk=org_id)
```

When dispatching:
```python
do_something.delay(
    tenant_schema=request.tenant.schema_name,
    org_id=org.id,
)
```

### Issue: Test failures with multi-tenant setup

Cause: Test database not initialized with tenant schemas.

Check conftest.py has proper setup:
```python
@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("migrate_schemas", "--shared", "--no-input")
```

### Issue: Signal handler runs in wrong schema

Cause: Signal fires in current schema; if signal handler accesses another schema, it fails.

Fix: Don't cross schemas in signal handlers. If cross-schema work needed, dispatch to Celery task.

### Issue: Admin shows no data

Cause: Admin ran in public schema; data is in tenant schemas.

Fix: For tenant data, access via tenant_command or configure admin to show active tenant data.

### Issue: Cannot drop schema (tenant deletion)

Cause: Open connections to schema or data dependencies.

Check:
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'mydb' AND pid <> pg_backend_pid();
```

Fix: Close connections, then drop:
```python
tenant.delete()  # Django auto-drops schema if auto_drop_schema=True
```

## Tenant Isolation Verification

If you suspect a data leak between tenants, run isolation tests:

```python
# tests/test_tenant_isolation.py

from django_tenants.utils import schema_context

def test_no_cross_tenant_data_leak():
    # Create tenant A with sensitive data
    with schema_context("a"):
        Organization.objects.create(name="Secret Org A")

    # Create tenant B with different data
    with schema_context("b"):
        Organization.objects.create(name="Org B")

    # Verify A can't see B's data
    with schema_context("a"):
        names = set(Organization.objects.values_list("name", flat=True))
        assert "Org B" not in names
        assert "Secret Org A" in names
```

Run isolation tests regularly:
```bash
poetry run pytest -m tenant_isolation
```

## Performance Issues

### Slow queries in tenant context

Check query plan in tenant schema:

```python
from django.db import connection
with schema_context("tenant_a"):
    print(Organization.objects.all().explain())
```

Ensure indexes exist in tenant schema (may need to add to specific migrations).

### Many tenants = slow migrations

Running `migrate_schemas` on 100+ tenants can take time. Options:
- Parallelize (django-tenants supports it)
- Schedule during low-traffic window
- For non-critical migrations, defer and run tenant-by-tenant

```bash
# Parallel migrations
poetry run python manage.py migrate_schemas --executor=multiprocessing
```

## Tenant Creation Issues

### Schema creation fails

Check Postgres user has `CREATE` privilege:
```sql
GRANT CREATE ON DATABASE mydb TO myuser;
```

### Domain validation fails

Check domain format and DNS resolution:
- Must be valid hostname
- No ports or paths
- DNS must resolve (for production)

## Debugging Toolkit

### Django shell with tenant context

```bash
poetry run python manage.py tenant_command shell --schema=acme
```

### SQL query log in tenant context

```python
from django.db import connection

with schema_context("acme"):
    # Run queries
    for q in connection.queries:
        print(q["sql"])
```

### Inspect tenant cache state

```python
from django.core.cache import cache
cache.keys(f"tenant:{tenant.schema_name}:*")
```

## When to Escalate

If you've tried the above and issue persists:
- Document the symptoms, what you tried, and what you found
- Check related GitHub issues in django-tenants repo
- Consider whether the issue is django-tenants itself or your usage
