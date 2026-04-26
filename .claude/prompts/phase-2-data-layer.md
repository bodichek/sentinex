# Phase 2: Data Layer (Week 2)

## Goal

Connect Sentinex to real company data via Google Workspace MCP integration. Build the Data Access Layer with Insight Functions that aggregate real data into typed, agent-consumable outputs.

## Prerequisites

- Phase 1 complete and deployed
- Google Cloud project created (for OAuth)
- Google Workspace OAuth credentials (client ID, client secret)
- OpenAI API key working (for embeddings)

## Reference Materials

- `docs/DATA_ACCESS.md` — Data Access Layer design
- `.claude/skills/add-mcp-integration.md` — adding MCP integrations
- `.claude/skills/add-insight-function.md` — adding Insight Functions

## Deliverables

By end of Phase 2:

1. **MCP Gateway** functional and tested
2. **Google Workspace integration** working
   - OAuth connect flow (user can connect their Google account)
   - Encrypted credential storage
   - Token refresh handling
   - Calls to Gmail, Calendar, Drive working
3. **Sync pipelines**
   - Celery tasks for scheduled sync
   - Data minimization (metrics only, not raw content)
   - Event emission on sync complete
4. **5 Insight Functions implemented and tested**:
   - `get_weekly_metrics(org)`
   - `get_recent_anomalies(org)`
   - `get_team_activity_summary(org, period)`
   - `get_upcoming_commitments(org)`
   - `get_cashflow_snapshot(org)` (basic, without accounting integration — uses manually entered data)
5. **RAG infrastructure**
   - pgvector setup
   - Document ingestion pipeline
   - Semantic search working
6. **Agent integration**
   - Specialists use Insight Functions
   - Context Builder incorporates retrieved data
7. **Tests**
   - Insight Function unit tests with mock data
   - MCP Gateway integration tests
   - Sync pipeline tests

## Constraints

- Only Google Workspace MCP in this phase (no Microsoft, Slack, etc.)
- Store metrics, never raw data (emails, calendar contents)
- Never store PII in LLM logs
- All external calls go through MCP Gateway or API Client abstraction

## Step-by-Step Breakdown

### Step 2.1: Google Workspace MCP Integration

Connect Sentinex to Google Workspace via official Anthropic MCP server.

See: `prompts/07-google-workspace-mcp.md`

### Step 2.2: Insight Functions Implementation

Build the first 5 Insight Functions with real data from Google Workspace.

See: `prompts/08-insight-functions.md`

## Acceptance Criteria

Phase 2 is complete when:

1. **User can connect Google account**: OAuth flow works end-to-end
2. **Data syncs automatically**: scheduled task pulls Google Workspace data, stores metrics
3. **Insight Functions return real data**: querying `get_weekly_metrics` returns real, non-mocked values
4. **RAG works**: ingest a document, query it via semantic search
5. **Agents use Insight Functions**: Specialist agents call Insight Functions and produce informed responses
6. **Tests pass**: all Phase 2 tests green
7. **No PII leaks**: audit logs show no sensitive data, LLM prompts mask PII
8. **Docs updated**: `docs/DATA_ACCESS.md` reflects actual implementation

## What NOT to Do in Phase 2

- Don't add Microsoft 365, Slack, or other integrations (later phase)
- Don't build the Weekly Brief addon (Phase 3)
- Don't set up custom MCP servers (Pohoda, ABRA, etc. — later)
- Don't optimize RAG beyond basic functionality

## Verification

End of Phase 2 smoke test:

```bash
# 1. User flow (manual)
# - Log in as tenant user
# - Go to Integrations page
# - Click "Connect Google Workspace"
# - Authorize in Google OAuth
# - Return to Sentinex, see "Connected" status

# 2. Sync trigger
poetry run python manage.py tenant_command sync_integration \
  --schema=demo --integration=google_workspace

# 3. Verify data stored
poetry run python manage.py tenant_command shell --schema=demo
>>> from apps.data_access.models import DataSnapshot
>>> DataSnapshot.objects.filter(source="google_workspace").count()
# Should be > 0

# 4. Insight Function
>>> from apps.data_access.insight_functions import get_weekly_metrics
>>> from apps.core.models import Organization
>>> org = Organization.objects.first()
>>> metrics = get_weekly_metrics(org)
>>> print(metrics)
# Should show real aggregated metrics

# 5. Agent query with real data
# Via UI, submit query: "How was our last week?"
# Should receive response informed by Insight Functions
```

## Estimated Effort

- **Time**: 5 days working 8–16 hours each
- **Lines of code**: ~2000–4000
- **Complexity**: OAuth flow, encryption, async sync — non-trivial integration work

## Next Phase

Once Phase 2 is complete, move to:
- `.claude/prompts/phase-3-addon.md` — Build the CEO Weekly Brief addon

## Questions to Ask Before Starting

- Are Google OAuth credentials ready?
- Is the OAuth redirect URL configured in Google Cloud Console?
- Do you have a Google Workspace account for testing?
- Is encryption key (django-cryptography) configured?

If any of these is "no", address before starting Phase 2 implementation.

## Risk Factors

- **Google OAuth verification**: for production use, Google may require app verification. For MVP with single tenant/user, unverified OAuth works with "unverified app" warning. Plan for verification later.
- **MCP server stability**: official Anthropic MCP server is new, may have bugs. Have fallback strategy (direct Google API calls if MCP fails).
- **Rate limits**: Google APIs have quotas. Implement backoff.
