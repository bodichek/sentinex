# Prompt 10: CEO Weekly Brief Addon

## Goal

Build the first production-grade addon: CEO Weekly Brief. Structured Monday morning briefing delivered via email and web dashboard, with PDF export.

## Prerequisites

- Prompt 09 complete (Addon framework works)

## Context

This is the wedge product. One addon, done exceptionally well. Pattern for all future addons. See `docs/ADDONS.md` and `.claude/skills/create-addon.md`.

## Constraints

- Addon at `apps/addons/weekly_brief/`
- No direct core DB access (use services and Insight Functions)
- Generation asynchronous (Celery task)
- Idempotent (re-running doesn't duplicate briefs)
- Per-tenant timezone respected for scheduled generation

## Deliverables

1. Full addon structure at `apps/addons/weekly_brief/`:
   ```
   weekly_brief/
   ├── __init__.py
   ├── apps.py              # WeeklyBriefConfig with on_activate/on_deactivate
   ├── manifest.py          # AddonManifest
   ├── models.py
   ├── migrations/
   ├── services.py          # WeeklyBriefGenerator
   ├── prompts/
   │   └── brief_composer.yaml
   ├── views.py
   ├── urls.py
   ├── api.py
   ├── tasks.py
   ├── events.py
   ├── templates/addons/weekly_brief/
   │   ├── base.html
   │   ├── home.html
   │   ├── brief_detail.html
   │   ├── history.html
   │   ├── configure.html
   │   └── email/
   │       ├── brief.html
   │       └── brief.txt
   ├── pdf_generator.py     # PDF export via weasyprint or similar
   └── tests/
       ├── test_services.py
       ├── test_tasks.py
       ├── test_views.py
       └── test_integration.py
   ```
2. Models:
   - `WeeklyBriefConfig` (tenant schema): recipients, schedule_day, schedule_hour (local time), sections_enabled, timezone
   - `WeeklyBriefReport` (tenant schema): period_start, period_end, content JSONField, html_body, plain_body, status, generated_at, delivered_at
3. `WeeklyBriefGenerator` service:
   - Fetches data from Insight Functions:
     - `get_weekly_metrics`
     - `get_recent_anomalies`
     - `get_team_activity_summary`
     - `get_upcoming_commitments`
     - `get_cashflow_snapshot`
   - Composes structured content (dict with sections)
   - Uses LLM (Orchestrator) to write executive summary in natural language
   - Renders email (HTML + plain text)
   - Stores `WeeklyBriefReport`
4. Celery tasks:
   - `generate_weekly_brief_for_tenant(tenant_schema)` — generate and store
   - `send_weekly_brief_email(report_id)` — deliver email
5. Celery Beat schedule:
   - For each active tenant with weekly_brief enabled, schedule per configured day/hour in tenant's timezone
   - Use `django-celery-beat` with PeriodicTask created per tenant on addon activation
6. Views:
   - `/addons/weekly-brief/` — home, shows latest brief
   - `/addons/weekly-brief/history/` — past briefs list
   - `/addons/weekly-brief/<uuid>/` — specific brief detail
   - `/addons/weekly-brief/<uuid>/pdf/` — PDF export
   - `/addons/weekly-brief/configure/` — configuration
7. API:
   - `POST /addons/weekly-brief/api/generate/` — manually trigger generation
   - `GET /addons/weekly-brief/api/reports/` — list reports
8. Email delivery:
   - Use Django's `send_mail` with configured backend
   - In dev: console backend
   - In prod: SMTP or transactional email service
9. PDF generation:
   - Use `weasyprint` (HTML-to-PDF)
   - Styled with Tailwind (or inline CSS for PDF)
10. Lifecycle hooks in `WeeklyBriefConfig.on_activate`:
    - Create default `WeeklyBriefConfig` for tenant
    - Create PeriodicTask for scheduled generation
11. Management command `generate_weekly_brief --tenant <>` for manual testing
12. Tests:
    - Service generates brief with mocked Insight Functions
    - Task runs end-to-end (with test LLM)
    - Email rendering
    - PDF generation
    - Tenant isolation
    - Schedule creation on activation
    - Idempotency (generating twice for same week returns existing)
13. Documentation:
    - `docs/addons/weekly_brief.md` — addon-specific docs

## Acceptance Criteria

- Activating the addon creates a `WeeklyBriefConfig` for the tenant
- Admin can configure recipients and schedule
- Manual generation command produces a report
- Report visible in web UI with all sections
- Report deliverable via email (check console in dev)
- PDF export works
- Scheduled generation runs at configured time
- Tests pass
- `mypy` strict passes for addon code

## Next Steps

After this prompt, Phase 3 is complete. Proceed to `phase-4-pilot.md` → `11-deployment.md`.

## Notes for Claude Code

- `brief_composer.yaml` prompt instructs LLM: "Given this structured data about a company's past week, write an executive summary in 3-5 paragraphs covering: key developments, notable anomalies, upcoming priorities. Be direct, data-driven, no fluff."
- LLM returns natural language; we render the final brief combining structured data + natural language summary
- Email template: clean, minimal, inline CSS (not all clients render Tailwind classes)
- PDF template: similar to email but richer formatting
- Timezone handling: store tenant's timezone in `WeeklyBriefConfig`; use `pytz` or Python 3.12's `zoneinfo`
- Celery Beat: use `django-celery-beat` with DB-backed scheduler (not file-based)
- Idempotency: check for existing report with same `period_start` before creating new
- Consider: do weekly briefs always cover Monday-Sunday of previous week, or last 7 days from generation date? Pick one and document.
