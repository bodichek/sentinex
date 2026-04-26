# Pilot Onboarding

Step-by-step procedure for onboarding a new pilot customer onto Sentinex.

## Prerequisites (before kickoff call)

Confirm with the pilot CEO:
- They have a **Google Workspace** account with permission to grant read-only
  OAuth access to Gmail, Calendar, Drive.
- They can provide a short **company identifier** for the tenant schema
  (lowercase, a–z/0–9/underscore, e.g. `acme_cz`).
- They have a delivery **email address** for the Weekly Brief.
- They can commit to a **30-minute feedback call** 7 days after the first
  scheduled brief.

## 1. Create the tenant (operator, ~2 min)

```bash
poetry run python manage.py create_tenant \
    --schema_name <schema> \
    --name "<Company Name>" \
    --is_active True \
    --domain-domain <schema>.sentinex.cz \
    --domain-is_primary True \
    --noinput
```

Or run the one-shot helper:

```bash
poetry run python manage.py onboard_pilot \
    --schema <schema> \
    --name "<Company Name>" \
    --domain <schema>.sentinex.cz \
    --owner-email <ceo@example.com>
```

The helper creates the tenant, the primary domain, activates the
`weekly_brief` addon, and emits an owner-role invitation. The invitation URL
is printed to stdout — paste it into the welcome email.

## 2. Send the welcome email (operator, ~5 min)

Use the template at `docs/onboarding_emails/welcome.md`. Include:

- Tenant URL: `https://<schema>.sentinex.cz/`
- Invitation link (from previous step)
- Scheduled kickoff call time
- Your direct contact (WhatsApp / phone)

## 3. Kickoff call (operator + CEO, ~30 min)

Walk the CEO through:

1. **Log in** — click invitation link, set password.
2. **Connect Google Workspace** — Integrations → "Připojit Google Workspace".
   Ensure OAuth consent completes and `Integration.is_active == True`.
3. **Trigger first sync** —
   `python manage.py shell -c "from apps.data_access.tasks import sync_google_workspace_for_tenant; sync_google_workspace_for_tenant.delay('<schema>')"`
4. **Enter baseline KPIs** — admin → ManualKPI → at minimum:
   `cash_on_hand`, `monthly_expenses`, ideally `revenue`.
5. **Configure Weekly Brief** — `/addons/weekly-brief/configure/` — recipients,
   day (0 = Monday), hour (local time), timezone (default `Europe/Prague`).
6. **Preview first brief** — manual trigger:
   `python manage.py generate_weekly_brief --tenant <schema>`
   Verify email arrives, UI renders, PDF downloads.

## 4. Scheduled delivery (automatic)

Celery Beat fires `weekly_brief.generate_weekly_brief_for_tenant(<schema>)`
per the configured schedule; `send_weekly_brief_email` follows on success.

## 5. Daily check during pilot week (operator, ~5 min/day)

- Sentry dashboard — zero-error baseline for the pilot tenant.
- `python manage.py healthcheck` — DB + cache status.
- `python manage.py list_active_addons --tenant <schema>` — activations stable.
- Tail Celery worker logs for the pilot's tasks.

## 6. Feedback session (operator + CEO, ~30 min, D+7)

Use the question list in this doc's appendix. Log notes in
`docs/pilots/<pilot_name>/log.md`. Categorize follow-ups:

- **P0** — blocker or data loss. Fix within 48 h.
- **P1** — important UX / content gap. Fix within 1 week.
- **P2** — nice-to-have. Add to backlog.

## 7. Retrospective (operator, ~45 min, D+14)

Write to `docs/retrospectives/pilot-<n>.md` with sections:
what worked, what didn't, what to change for the next pilot.

## Appendix: Feedback questions

1. První dojem z platformy?
2. Co v reportu bylo nejužitečnější?
3. Co bylo matoucí nebo irelevantní?
4. Projdeme sekci po sekci — které si necháte, které vyhodíte?
5. Co chybí, aby pro vás report měl hodnotu **4 000 Kč / měsíc**?
6. Pokračovali byste další 3 měsíce?
