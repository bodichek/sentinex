# Addon Development Guide

## What is an Addon

An addon is a self-contained Django app that extends Sentinex with specific functionality. Examples: CEO Weekly Brief, Quarterly Planning Cockpit, Cash Flow Dashboard.

Addons are modular. Activating or deactivating an addon per tenant should not affect other addons or the core platform.

## Addon Rules

1. An addon is a Django app located in `apps/addons/<addon_name>/`.
2. An addon must have a `manifest.py` file at its root describing metadata.
3. An addon MUST NOT access core database tables directly. It communicates with core via:
   - REST API calls to core endpoints
   - Subscribing to events via Django signals or Celery tasks
   - Calling registered Insight Functions from `apps.data_access`
4. An addon MUST NOT depend on another addon directly. Cross-addon communication happens via the event bus.
5. An addon has its own migrations, models, views, templates, URLs, and tests.
6. An addon is activated per tenant via the addon registry (feature flags).

## Addon Structure

```
apps/addons/<addon_name>/
├── __init__.py
├── apps.py                 # Django AppConfig with addon metadata
├── manifest.py             # Addon manifest (metadata, pricing, config schema)
├── models.py               # Addon-specific models (tenant schema)
├── migrations/             # Migrations for addon models
├── agents.py               # Addon-specific agents (optional)
├── prompts/                # YAML system prompts for agents
├── insight_functions.py    # Addon-specific Insight Functions (optional)
├── api.py                  # REST endpoints for addon
├── urls.py                 # URL routing under /addons/<addon_name>/
├── views.py                # UI views
├── templates/              # HTML templates
│   └── addons/<addon_name>/
├── events.py               # Event subscriptions
├── tasks.py                # Celery tasks (scheduled or ad-hoc)
├── permissions.py          # Addon-level permissions
├── services.py             # Business logic layer
└── tests/                  # Unit and integration tests
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

## Manifest

Every addon declares its metadata in `manifest.py`:

```python
# apps/addons/weekly_brief/manifest.py

from apps.core.addons import AddonManifest

manifest = AddonManifest(
    name="weekly_brief",
    display_name="CEO Weekly Brief",
    version="0.1.0",
    description="Monday morning structured briefing for CEOs",
    author="Sentinex",
    category="reporting",
    tags=["reporting", "weekly", "ceo"],
    pricing={
        "monthly": 1500,  # CZK per month
        "setup": 0,
    },
    dependencies={
        "core_version": ">=0.1.0",
        "insight_functions": [
            "get_weekly_metrics",
            "get_recent_anomalies",
            "get_team_activity_summary",
            "get_upcoming_commitments",
        ],
    },
    permissions=[
        "weekly_brief.view",
        "weekly_brief.configure",
    ],
    ui_entry_points=[
        {"label": "Weekly Brief", "url_name": "weekly_brief:home"},
    ],
)
```

## Creating a New Addon

### 1. Generate scaffolding

```bash
poetry run python manage.py create_addon <addon_name>
```

This creates the directory structure and boilerplate files.

### 2. Declare in settings

Add to `config/settings/base.py`:

```python
INSTALLED_APPS = [
    # ...
    "apps.addons.<addon_name>",
]
```

### 3. Write manifest

Fill in `manifest.py` with real values.

### 4. Define models

If the addon has its own data:

```python
# apps/addons/<addon_name>/models.py

from django.db import models

class AddonConfig(models.Model):
    """Per-tenant configuration for this addon."""
    # Tenant resolution is automatic via django-tenants

    schedule_day = models.IntegerField(default=1)  # Monday
    schedule_hour = models.IntegerField(default=7)
    recipients = models.JSONField(default=list)

    class Meta:
        verbose_name = "Weekly Brief Config"
```

### 5. Create migrations

```bash
poetry run python manage.py makemigrations <addon_name>
poetry run python manage.py migrate_schemas
```

### 6. Implement business logic in services

Keep logic out of views:

```python
# apps/addons/<addon_name>/services.py

from apps.data_access.insight_functions import get_weekly_metrics
from apps.agents.orchestrator import Orchestrator

class WeeklyBriefGenerator:
    def __init__(self, organization):
        self.org = organization

    def generate(self) -> dict:
        metrics = get_weekly_metrics(self.org)
        # ... use Insight Functions, agents, etc.
        return brief_data
```

### 7. Schedule tasks

For scheduled addons, use Celery Beat:

```python
# apps/addons/<addon_name>/tasks.py

from celery import shared_task
from apps.core.models import Organization
from .services import WeeklyBriefGenerator

@shared_task
def generate_weekly_brief(org_id: int):
    org = Organization.objects.get(pk=org_id)
    generator = WeeklyBriefGenerator(org)
    brief = generator.generate()
    # send email, store in DB, etc.
```

Schedule registered in `config/celery.py` or via database (django-celery-beat).

### 8. Expose UI

Create views and templates under `templates/addons/<addon_name>/`. Register URLs in `urls.py`:

```python
# apps/addons/<addon_name>/urls.py

from django.urls import path
from . import views

app_name = "weekly_brief"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("history/", views.HistoryView.as_view(), name="history"),
    path("configure/", views.ConfigureView.as_view(), name="configure"),
]
```

Include in main URL config:

```python
# config/urls.py

path("addons/weekly-brief/", include("apps.addons.weekly_brief.urls")),
```

### 9. Write tests

Minimum:
- Test addon activation/deactivation
- Test tenant isolation
- Test core business logic
- Test at least one happy path end-to-end

### 10. Activate for tenant

```bash
poetry run python manage.py activate_addon --tenant <tenant> --addon <addon_name>
```

## Event Bus

### Subscribing to events

```python
# apps/addons/<addon_name>/events.py

from django.dispatch import receiver
from apps.core.events import data_synced

@receiver(data_synced)
def on_data_synced(sender, organization, source, **kwargs):
    # React to data sync events
    pass
```

### Emitting events

```python
from apps.core.events import addon_event

addon_event.send(
    sender=self.__class__,
    addon="weekly_brief",
    event_type="brief_generated",
    payload={"org_id": org.id, "date": date.today()},
)
```

## Testing Addons

### Unit tests

Standard Django / pytest tests. Test services and models in isolation.

### Integration tests

Test the full flow including core dependencies:

```python
# apps/addons/<addon_name>/tests/test_integration.py

import pytest
from django.test import TenantTestCase

class WeeklyBriefIntegrationTest(TenantTestCase):
    def test_brief_generation_end_to_end(self):
        # Setup tenant, organization, connected data sources
        # Trigger brief generation
        # Assert output
        pass
```

### Tenant isolation tests

Every addon must verify it does not leak data across tenants:

```python
def test_addon_respects_tenant_isolation(self):
    # Create two tenants with data
    # Run addon logic for tenant A
    # Assert tenant B data not accessed or affected
    pass
```

## Pricing and Billing Integration

Addons declare pricing in `manifest.py`. Core billing system reads this to compute monthly invoices.

For MVP, billing is manual — admin reviews addon activations and creates invoices.

## Lifecycle Hooks

Addons can implement lifecycle hooks in `apps.py`:

```python
from django.apps import AppConfig

class WeeklyBriefConfig(AppConfig):
    name = "apps.addons.weekly_brief"

    def ready(self):
        from . import events  # Register signal handlers

    def on_activate(self, tenant):
        """Called when addon is activated for a tenant."""
        # Setup default config, schedule tasks
        pass

    def on_deactivate(self, tenant):
        """Called when addon is deactivated for a tenant."""
        # Cancel scheduled tasks, cleanup
        pass
```

## Addon Checklist

Before merging a new addon:

- [ ] Manifest declared and complete
- [ ] Models have migrations
- [ ] Business logic in services, not views
- [ ] Tests cover happy path and tenant isolation
- [ ] No direct core DB access
- [ ] No direct dependency on other addons
- [ ] Documentation in `docs/addons/<addon_name>.md` (optional but recommended)
- [ ] Feature flag activation works
- [ ] Lifecycle hooks implemented if needed
