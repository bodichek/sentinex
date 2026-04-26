# Skill: Create New Addon

Use this skill when adding a new addon to Sentinex.

## When to Use

- User requests a new addon (e.g., "Create a Quarterly Planning addon")
- Feature request that represents a distinct functional module
- Expanding Sentinex's addon catalog

## Prerequisites

- Core platform is installed and running
- Understanding of the addon contract (see `docs/ADDONS.md`)
- Name for the new addon (snake_case)

## Steps

### 1. Verify requirements

Before creating, confirm:
- Is this really an addon or a core feature?
- Does it have distinct user value?
- Does it avoid creating tight coupling with other addons?

If it fits the addon criteria, proceed.

### 2. Generate scaffolding

Create the addon directory structure:

```
apps/addons/<addon_name>/
├── __init__.py
├── apps.py
├── manifest.py
├── models.py
├── migrations/
│   └── __init__.py
├── services.py
├── views.py
├── urls.py
├── api.py
├── tasks.py
├── events.py
├── permissions.py
├── prompts/
├── templates/addons/<addon_name>/
│   ├── base.html
│   └── home.html
└── tests/
    ├── __init__.py
    ├── test_services.py
    └── test_integration.py
```

### 3. Write manifest

Create `manifest.py` with metadata:

- `name`: snake_case identifier
- `display_name`: human-readable name
- `version`: start with "0.1.0"
- `description`: one-sentence summary
- `category`: e.g., "reporting", "planning", "monitoring"
- `dependencies`: required Insight Functions
- `pricing`: monthly cost in CZK, setup fee

### 4. Implement models (if needed)

If the addon has configuration or data:
- Add models to `models.py`
- Ensure models work within tenant schemas
- Create migrations

### 5. Register in settings

Add to `config/settings/base.py`:
```python
INSTALLED_APPS = [
    # ...
    "apps.addons.<addon_name>",
]

TENANT_APPS = [
    # ...
    "apps.addons.<addon_name>",
]
```

### 6. Implement services

Put business logic in `services.py`, not views. Services are testable, reusable, composable.

### 7. Wire up UI

- Add URL patterns in `urls.py`
- Include in `config/urls.py`
- Create views and templates
- Use HTMX for interactivity

### 8. Add scheduled tasks (if needed)

If the addon has scheduled work (like weekly briefs):
- Create Celery task in `tasks.py`
- Register schedule in `config/celery.py` or via django-celery-beat

### 9. Write tests

Required:
- Service unit tests
- Integration test for core flow
- Tenant isolation test

### 10. Document

- Update `docs/ADDONS.md` if needed
- Consider adding `docs/addons/<addon_name>.md` for detailed addon docs

### 11. Migrate and activate

```bash
poetry run python manage.py makemigrations <addon_name>
poetry run python manage.py migrate_schemas
poetry run python manage.py activate_addon --tenant <test_tenant> --addon <addon_name>
```

### 12. Manual test

Log in as tenant user, activate the addon, verify functionality.

## Common Mistakes to Avoid

- Adding direct DB access to core models (forbidden — use API)
- Depending on another addon directly (forbidden — use events)
- Putting business logic in views
- Forgetting to add tests
- Forgetting to update manifest

## Verification Checklist

- [ ] Directory structure correct
- [ ] Manifest complete
- [ ] Models have migrations (if any)
- [ ] Services contain business logic
- [ ] Views are thin
- [ ] URLs registered
- [ ] Templates use Tailwind + HTMX
- [ ] Tests written (service, integration, tenant isolation)
- [ ] No direct core DB access
- [ ] No direct cross-addon dependency
- [ ] Documentation updated
