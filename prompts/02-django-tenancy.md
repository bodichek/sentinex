# Prompt 02: Django Tenancy

## Goal

Configure `django-tenants` for schema-per-tenant isolation. Create Tenant and Domain models, middleware, and a management command to create tenants.

## Prerequisites

- Prompt 01 complete (project skeleton exists)
- PostgreSQL running locally

## Context

Multi-tenancy is foundational. Every downstream feature depends on correct tenant isolation. Schema-per-tenant gives us strong isolation and GDPR benefits. See `docs/TENANCY.md` for full rationale and design.

## Constraints

- Use `django-tenants` package
- Schema per tenant (not tenant_id column)
- Tenant model in `apps/core/`
- Never allow cross-tenant queries from application code
- Middleware resolves tenant from subdomain

## Deliverables

1. `django-tenants` added to Poetry dependencies
2. `apps/core/` Django app created
3. `Tenant` and `Domain` models in `apps/core/models.py`
4. Settings updated:
   - `SHARED_APPS` and `TENANT_APPS` defined
   - Tenancy middleware configured
   - Database router configured
   - `TENANT_MODEL` and `TENANT_DOMAIN_MODEL` pointed to core models
5. Migrations for Tenant and Domain (shared schema)
6. Management command `create_tenant` that interactively creates a tenant with domain
7. Management command `setup_postgres` that ensures pgvector extension exists
8. Management command `list_tenants` for ops
9. Basic `apps/core/admin.py` registering Tenant and Domain in Django admin
10. Tests for tenant creation and isolation in `apps/core/tests/test_tenancy.py`

## Acceptance Criteria

- `poetry run python manage.py migrate_schemas --shared` creates shared tables
- `poetry run python manage.py create_tenant` produces a working tenant
- Subdomain routing works: accessing `<tenant>.sentinex.local:8000` resolves to tenant context
- Isolation test passes: data in tenant A not visible from tenant B context
- Admin can list all tenants (while in public schema)
- `list_tenants` command prints all tenants with status

## Next Steps

After this prompt, proceed to `03-auth-basic.md`.

## Notes for Claude Code

- `auto_create_schema = True` and `auto_drop_schema = True` on Tenant model (useful for dev; revisit for prod)
- Use `django-tenants` `TenantMainMiddleware` at the top of middleware stack
- Database config must use `django_tenants.postgresql_backend` engine
- For local dev, use `*.sentinex.local` entries in `/etc/hosts` (document in DEVELOPMENT.md)
- Test using `django_tenants.test.cases.TenantTestCase` or pytest fixtures that set schema context
- Make sure `sites` framework is in `SHARED_APPS` if needed (usually yes)
- Create `public` tenant by default during `migrate_schemas --shared`
