# Skill: Create Migration

Use this skill when creating Django migrations in Sentinex's multi-tenant setup.

## When to Use

- Adding a new model
- Modifying existing model (new field, changed field, etc.)
- Removing a model or field
- Data migrations

## Critical Rules

1. **Migrations must be backward-compatible** during zero-downtime deploys
2. **Tenant migrations must run for every tenant** — be aware of performance
3. **Destructive changes require two-step migrations** (add new, migrate data, drop old)
4. **Never use `--fake-initial` in production** without understanding the consequences

## Steps

### 1. Determine schema scope

Is the model shared or tenant-specific?

**Shared (public schema)**:
- Users, auth, billing, audit logs
- Add model to an app in `SHARED_APPS`

**Tenant-specific**:
- Business data, addon data, conversations
- Add model to an app in `TENANT_APPS`

### 2. Create model

Example tenant model:
```python
# apps/data_access/models.py

from django.db import models

class DataSnapshot(models.Model):
    source = models.CharField(max_length=50)
    period_end = models.DateField()
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "period_end"]),
        ]
```

### 3. Generate migration

```bash
poetry run python manage.py makemigrations <app_name>
```

Review the generated file. Check:
- Migration name is descriptive
- Fields match model definition
- Indexes created
- Dependencies correct

### 4. Review for backward compatibility

Answer these questions:

**Adding a column?**
- Nullable or has default? → OK, safe
- Non-nullable without default? → NOT SAFE, requires two-step

**Dropping a column?**
- Old code still using it? → NOT SAFE, stop using in code first, then drop in next release
- Fully unused? → OK

**Renaming a column?**
- Old code still using old name? → Two-step required:
  1. Add new column, copy data, keep both
  2. Update code to use new column
  3. Drop old column in next release

**Changing a field type?**
- Usually requires migration with data transformation
- Test carefully with production-like data

### 5. Test migration

```bash
# Fresh database
docker-compose down -v
docker-compose up -d postgres
poetry run python manage.py setup_postgres
poetry run python manage.py migrate_schemas --shared
poetry run python manage.py migrate_schemas
```

Verify:
- Migration runs without errors
- Schema correct after migration
- Existing tests still pass

### 6. Test backward compatibility

Deploy strategy:
1. Deploy new code with migration (old code still running)
2. Migration runs during deploy
3. Old code should still work against new schema
4. New code benefits from new schema

Verify this by:
- Running old test suite against new schema
- Deploy to staging and check old endpoints work

### 7. Apply to all tenants

```bash
# Applies to all tenant schemas
poetry run python manage.py migrate_schemas
```

If tenant-specific migration needs special handling (data migration), apply to one tenant first to verify.

### 8. Rollback plan

Every migration should be reversible where possible:

```python
# In migration file
operations = [
    migrations.AddField(
        model_name="organization",
        name="industry",
        field=models.CharField(max_length=100, null=True),
    ),
]
```

Django auto-generates reverse operations for most cases.

For data migrations, write reverse explicitly:
```python
operations = [
    migrations.RunPython(
        forward_func,
        reverse_func,
    ),
]
```

### 9. Document special migrations

For complex migrations, add a comment explaining:
- What the migration does
- Why it was needed
- Any manual steps required
- Rollback procedure

Example:
```python
# This migration converts the `status` field from IntegerField to CharField.
# Two-step migration:
# 1. This file adds the new `status_new` CharField
# 2. Next deploy (next-migration.py) drops `status` and renames `status_new` to `status`
# 3. Code updated in between to use `status_new`
```

## Data Migrations

For data transformations:

```python
from django.db import migrations

def forward(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    for org in Organization.objects.all():
        # Transform data
        org.industry = derive_industry(org.name)
        org.save()

def reverse(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    Organization.objects.update(industry=None)

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_add_industry_field"),
    ]
    operations = [
        migrations.RunPython(forward, reverse),
    ]
```

Use `apps.get_model()` to avoid issues with model changes in future migrations.

## Common Pitfalls

### Forgetting to migrate tenants

If you add a field to a tenant model but only run `migrate_schemas --shared`, tenants won't have the new field. Always run `migrate_schemas` after `--shared`.

### Non-nullable fields without defaults

Django will prompt you to provide a default when running migrations. Don't just accept the default — think about what value is meaningful.

### Circular dependencies

If migration A depends on B and B depends on A, Django can't order them. Refactor to break the cycle.

### Long-running migrations

Migrations that take minutes on millions of rows will time out or block deploys. For large data migrations:
- Break into batches
- Run outside of migration system (custom management command)
- Consider dual-write pattern for zero downtime

## Verification Checklist

- [ ] Migration generated
- [ ] Reviewed for backward compatibility
- [ ] Applied to fresh DB successfully
- [ ] Applied to all tenants successfully
- [ ] Existing tests still pass
- [ ] New tests added if schema affects business logic
- [ ] Rollback procedure understood
- [ ] Complex migrations documented
