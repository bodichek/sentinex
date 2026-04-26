# Prompt 07: Google Workspace MCP Integration

## Goal

Connect Sentinex to Google Workspace via the official Anthropic MCP server. Build OAuth flow, encrypted credential storage, MCP Gateway wrapper, and basic sync pipeline.

## Prerequisites

- Phase 1 complete
- Google Cloud project created
- OAuth 2.0 credentials configured (client ID, secret)
- Authorized redirect URI set to `https://<tenant>.sentinex.<tld>/integrations/google_workspace/callback/`
- For dev: `http://<tenant>.sentinex.local:8000/integrations/google_workspace/callback/`

## Context

The first real integration. This sets the pattern for all future MCP integrations. See `docs/DATA_ACCESS.md` section "MCP Gateway" and skill `.claude/skills/add-mcp-integration.md`.

## Constraints

- Use official Anthropic Google Workspace MCP server (don't roll custom)
- OAuth tokens encrypted at rest via `django-cryptography`
- Token refresh happens proactively (5-min buffer before expiry)
- Per-tenant credentials (tenant A's tokens never accessible from tenant B)
- Rate limiting per tenant

## Deliverables

1. `django-cryptography` added to dependencies
2. `apps/data_access/` Django app (tenant-scoped)
3. `apps/data_access/mcp/` submodule:
   - `base.py` — `MCPIntegration` abstract class
   - `gateway.py` — `MCPGateway` class
   - `integrations/google_workspace.py` — Google Workspace integration
4. Models (tenant schema):
   - `Credential` with encrypted `oauth_tokens` JSONField
   - `Integration` tracking active integrations per tenant
   - `MCPCall` audit log
5. OAuth flow views:
   - `/integrations/` — list integrations, connect/disconnect
   - `/integrations/google_workspace/connect/` — initiate OAuth
   - `/integrations/google_workspace/callback/` — handle callback
6. Templates (minimal Tailwind UI):
   - `integrations/list.html`
   - `integrations/connect.html`
7. MCP Gateway features:
   - `call(integration, tool, params, tenant)` method
   - Credential retrieval and decryption
   - Token refresh if needed
   - MCP server invocation (subprocess or HTTP)
   - Audit log for every call
   - Rate limit enforcement (basic: per-tenant per-minute)
8. Sync pipeline:
   - `apps/data_access/sync/google_workspace.py`
   - Celery task `sync_google_workspace_for_tenant(tenant_schema)`
   - Fetches recent data (last 7 days by default)
   - Computes metrics (email count, unique senders, calendar event count, etc.)
   - Stores in `DataSnapshot` (tenant schema)
9. `DataSnapshot` model for computed metrics:
   - `source` (string: "google_workspace")
   - `period_start`, `period_end` dates
   - `metrics` JSONField
   - `created_at`
10. Admin views for `Integration`, `Credential` (read-only, no raw tokens shown), `MCPCall`
11. Tests:
    - OAuth URL generation
    - Callback handling (mocked Google response)
    - Token encryption/decryption
    - MCP Gateway call (mocked MCP server)
    - Sync pipeline (mocked data)
    - Tenant isolation

## Acceptance Criteria

- User logs in, visits `/integrations/`, clicks "Connect Google Workspace"
- Redirected to Google OAuth consent screen
- After consent, redirected back to Sentinex with "Connected" status
- Integration shows up as active in tenant's integration list
- Celery task `sync_google_workspace_for_tenant` runs successfully
- `DataSnapshot` records appear in tenant schema with real metrics
- Admin can review `MCPCall` log
- Tenant A cannot see tenant B's credentials or calls
- Tests pass

## Next Steps

After this prompt, proceed to `08-insight-functions.md`.

## Notes for Claude Code

- Google OAuth scopes needed (minimum): `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/calendar.readonly`, `https://www.googleapis.com/auth/drive.readonly`
- Use `offline_access` for refresh tokens
- Anthropic MCP server for Google Workspace: check docs for exact package name and invocation
- If MCP server requires running as subprocess, manage it via a pool or per-call spawn (per-call simpler for MVP)
- Store tokens in `oauth_tokens` JSONField with structure: `{"access_token": "...", "refresh_token": "...", "expires_at": "2026-04-22T15:00:00Z"}`
- Never log raw tokens; log only token presence and refresh events
- Rate limit: use Redis with sliding window (`redis-cell` or custom)
- Google Workspace API quotas: generous for read operations, respect them
