# Prompt 09: Addon Framework

## Goal

Build the Addon Registry framework: discovery, activation per tenant, manifest parsing, event bus. This is the foundation for all addons.

## Prerequisites

- Phase 2 complete (data layer functional)

## Context

Sentinex is addon-centric. Core is stable. Addons extend functionality. The framework must support adding addons without core changes. See `docs/ADDONS.md`.

## Constraints

- Addons are Django apps in `apps/addons/<n>/`
- Addons discovered via `INSTALLED_APPS` scan
- Activation per tenant via feature flags
- Addons communicate with core only via REST API or event bus
- No direct cross-addon dependencies

## Deliverables

1. `apps/core/addons/` module:
   - `manifest.py` — `AddonManifest` dataclass
   - `registry.py` — `AddonRegistry` class (discovers, tracks, activates addons)
   - `decorators.py` — `@addon_required` decorator for views
   - `events.py` — event definitions and dispatcher
2. `AddonManifest` dataclass:
   - `name`, `display_name`, `version`, `description`
   - `author`, `category`, `tags`
   - `pricing` (dict with monthly, setup fees)
   - `dependencies` (other addons or insight functions required)
   - `permissions` (list of permission strings)
   - `ui_entry_points` (list of {label, url_name})
3. Addon discovery:
   - On startup, scan `INSTALLED_APPS` for apps in `apps.addons.*`
   - Read each addon's `manifest.py`
   - Register in memory
4. Per-tenant activation:
   - `AddonActivation` model (public schema): tenant, addon_name, active, activated_at, config JSONField
   - Management command `activate_addon --tenant <> --addon <>`
   - Management command `deactivate_addon --tenant <> --addon <>`
   - Management command `list_addons` (all discovered) and `list_active_addons --tenant <>`
5. Feature flags:
   - `apps/core/feature_flags.py`
   - `is_enabled(tenant, feature_name) -> bool`
   - `enable(tenant, feature_name)` / `disable(tenant, feature_name)`
   - Caching (Redis, 5-min TTL)
6. Event bus:
   - Django signals defined in `apps/core/addons/events.py`:
     - `addon_activated`
     - `addon_deactivated`
     - `data_synced`
     - `report_generated`
   - Celery-based async events for cross-process:
     - `dispatch_event(event_name, payload)` — fires signal and queues task
   - Addons subscribe via signal handlers
7. Admin for `AddonActivation` (manage per-tenant activations)
8. UI: tenant admin page at `/admin/addons/` listing available and active addons
9. Lifecycle hooks:
   - Addon's `apps.py` can define `on_activate(tenant)` and `on_deactivate(tenant)`
   - Registry calls these when activation state changes
10. Tests:
    - Discovery finds addons in `apps.addons.*`
    - Manifest parsing works
    - Activation/deactivation
    - Events fire correctly
    - Addon can subscribe to core event
    - Tenant isolation of activations

## Acceptance Criteria

- Adding a new addon (stub) and listing shows it
- Activating addon for tenant persists in DB
- Addon's `on_activate` hook fires
- Firing `data_synced` event triggers addon's subscribed handler
- Management commands work as expected
- Tests pass

## Next Steps

After this prompt, proceed to `10-weekly-brief-addon.md`.

## Notes for Claude Code

- `AddonRegistry` is a singleton, initialized at Django startup
- Use `django.apps.AppConfig.ready()` to trigger discovery
- `manifest.py` imports `AddonManifest` from core, creates instance, assigns to module variable `manifest`
- Registry reads `manifest` attribute from each addon module
- Caching feature flags crucial — many views check them
- Events: define as Django signals (sync); for async, wrap in Celery task that sends signal
- Keep event payloads simple (JSON-serializable)
- Document addon event schema in `docs/ADDONS.md`
