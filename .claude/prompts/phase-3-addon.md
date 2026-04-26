# Phase 3: First Addon — CEO Weekly Brief (Week 3)

## Goal

Build the first production-grade addon: CEO Weekly Brief. Every Monday morning at 07:00 (tenant timezone), the tenant's CEO receives a structured briefing of the past week and upcoming priorities.

## Prerequisites

- Phase 2 complete (data flowing, Insight Functions working)
- Google Workspace connected for at least one tenant
- Email delivery configured (SMTP or Resend account — not in MVP if manual testing only)

## Reference Materials

- `docs/ADDONS.md` — addon development guide
- `.claude/skills/create-addon.md` — creating new addons

## Deliverables

By end of Phase 3:

1. **Addon Registry framework** (if not done in Phase 1)
   - Discovery mechanism
   - Activation per tenant
   - Manifest parsing
2. **CEO Weekly Brief addon** at `apps/addons/weekly_brief/`
   - Manifest
   - Models (WeeklyBriefConfig, WeeklyBriefReport)
   - Services (brief generation)
   - Scheduled task (Celery Beat, Monday 07:00 per tenant timezone)
   - Email template (HTML + plain text)
   - Web dashboard view (history of briefs)
   - PDF export
3. **Brief content sections**:
   - Period summary (last 7 days)
   - Key metrics (from Insight Functions)
   - Recent anomalies
   - Team activity summary
   - Upcoming commitments (next 7 days)
   - Cashflow snapshot (if data available)
4. **Configuration UI**:
   - Tenant admin can configure
   - Schedule day/time
   - Recipients
   - Sections to include
5. **Tests**
   - Unit tests for services
   - Integration test (generate real brief for test tenant)
   - Tenant isolation test
   - Schedule test
6. **Documentation**
   - `docs/addons/weekly_brief.md` — addon-specific doc

## Constraints

- Follow addon rules: no direct core DB access, no cross-addon dependencies
- Use Tailwind + HTMX for UI
- Brief generation must be asynchronous (Celery task)
- Generation must be idempotent (safe to re-run for same week)
- Per-tenant timezone respected

## Step-by-Step Breakdown

### Step 3.1: Addon Framework

If addon registry not yet implemented, build it now.

See: `prompts/09-addon-framework.md`

### Step 3.2: Weekly Brief Addon Implementation

Build the CEO Weekly Brief end-to-end.

See: `prompts/10-weekly-brief-addon.md`

## Acceptance Criteria

Phase 3 is complete when:

1. **Addon activatable**: `activate_addon --tenant demo --addon weekly_brief` works
2. **Configuration accessible**: tenant admin sees config page in UI
3. **Scheduled generation**: Monday 07:00 tenant time, brief auto-generates
4. **Manual trigger**: admin can manually trigger brief generation for testing
5. **Email delivery**: brief email arrives in inbox with correct content
6. **Dashboard view**: web UI shows brief history
7. **PDF export**: PDF downloads correctly
8. **Real data**: brief reflects actual tenant data (not placeholders)
9. **Tests pass**: all Phase 3 tests green
10. **Docs updated**: `docs/ADDONS.md` and `docs/addons/weekly_brief.md` current

## What NOT to Do in Phase 3

- Don't build additional addons (Quarterly Planning, etc. — later)
- Don't add complex rich text editing
- Don't build addon marketplace UI
- Don't add white-label customization

## Verification

End of Phase 3 smoke test:

```bash
# 1. Activate addon for test tenant
poetry run python manage.py activate_addon --tenant demo --addon weekly_brief

# 2. Configure via UI
# Visit: http://demo.sentinex.local:8000/addons/weekly-brief/configure/
# Set recipients, schedule

# 3. Manual trigger
poetry run python manage.py generate_weekly_brief --tenant demo

# 4. Check email inbox (for configured recipient)
# Should receive email with brief content

# 5. Check web UI
# Visit: http://demo.sentinex.local:8000/addons/weekly-brief/
# Should see brief in history

# 6. Export PDF
# Click export button, download should start

# 7. Wait until Monday 07:00 (or set schedule to near-term for testing)
# Brief should auto-generate
```

## Estimated Effort

- **Time**: 5–7 days working 8–16 hours each
- **Lines of code**: ~2000–3000
- **Complexity**: integration of agents, data access, email, PDF, scheduling

## Next Phase

Once Phase 3 is complete, move to:
- `.claude/prompts/phase-4-pilot.md` — Polish, testing, first real pilot customer

## Questions to Ask Before Starting

- Who receives the first real brief (testing)?
- Which Insight Functions are critical vs. nice-to-have?
- What does the CEO actually want to see? (Can interview pilot customer if available)
- Is the timezone handling clear? (Browser timezone for UI, tenant-configured for scheduled tasks)

## Design Decisions to Make

- **Email content**: detailed or concise?
- **Fallback for missing data**: skip section, show placeholder, or error?
- **Language**: English default, Czech option for CZ tenants
- **Tone**: direct, analytical, actionable — NOT marketing/fluff

## Risk Factors

- **Low data quality in early brief**: first brief for a tenant may have sparse data (few days connected). Plan for graceful degradation.
- **Timezone bugs**: Celery Beat scheduling + tenant timezones is a classic source of bugs. Test thoroughly.
- **Email deliverability**: configure SPF, DKIM, DMARC if using custom domain. For MVP can use a service (Resend, Postmark) with their domain.
