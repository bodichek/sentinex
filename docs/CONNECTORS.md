# Connectors

Connectors are stand-alone Django apps under `apps/connectors/<provider>/`.
Each one owns its OAuth/credentials flow, MCP integration class, sync
pipeline and Celery tasks; **none** of them define their own database
tables — they reuse `Integration`, `Credential`, `MCPCall` and
`DataSnapshot` from `apps.data_access`.

## Conventions

```
apps/connectors/<provider>/
├── __init__.py
├── apps.py             AppConfig (label = "connectors_<provider>")
├── client.py           low-level API client (HTTP / SDK)
├── integration.py      MCPIntegration subclass — OAuth + call() dispatcher
├── sync.py             periodic pipeline → DataSnapshot
├── tasks.py            @shared_task wrappers + dispatch fan-out
├── views.py            OAuth install / callback / setup wizard
├── urls.py             /integrations/<provider>/...
└── tests/
```

URL mount lives in `config/urls.py`:
```python
path("integrations/slack/",         include("apps.connectors.slack.urls")),
path("integrations/smartemailing/", include("apps.connectors.smartemailing.urls")),
path("integrations/pipedrive/",     include("apps.connectors.pipedrive.urls")),
```

The MCP gateway picks up every connector via `apps/data_access/mcp/registry.py`.

Beat schedules live centrally in `config/settings/base.py` —
`connectors.<provider>.dispatch` fans a single tick out to every active
tenant that has the integration enabled.

## Existing connectors

### Slack (`apps.connectors.slack`)

| | |
|---|---|
| Auth | OAuth v2 (`SLACK_CLIENT_ID`/`SECRET`) — falls back to bot-token paste when unset |
| Token URL | `https://slack.com/api/oauth.v2.access` |
| Scopes | `channels:read`, `channels:history`, `groups:read/history`, `users:read[.email]`, `team:read`, `usergroups:read`, `reactions:read` |
| Sync schedule | every 6 h |
| Tools | `channels.list`, `channels.history`, `users.list`, `team.info`, `usergroups.list` |

### SmartEmailing (`apps.connectors.smartemailing`)

| | |
|---|---|
| Auth | HTTP Basic — username (account email) + API key, pasted in setup wizard |
| Base URL | `https://app.smartemailing.cz/api/v3` |
| Sync schedule | daily |
| Snapshot metrics | `audience` (total contacts, list count), `campaigns` (top-N by recency, aggregated open-rate / CTR) |
| Tools | `ping`, `contactlists.list`, `contacts.count`, `campaigns.list`, `campaign.stats` |

Setup: `/integrations/smartemailing/setup/` → user pastes username + API
key. The wizard pings the API before activating.

### Canva (`apps.connectors.canva`)

Canva is the first connector that talks to a real **MCP server**, not a
REST API. Auth is plain OAuth 2.1 + PKCE (so the same token works for the
Canva Connect REST API too); calls are dispatched over the **Streamable
HTTP** transport using the official `mcp` Python SDK.

| | |
|---|---|
| Auth | OAuth 2.1 + PKCE (`CANVA_CLIENT_ID`/`SECRET`) |
| Authorize URL | `https://www.canva.com/api/oauth/authorize` |
| Token URL | `https://api.canva.com/rest/v1/oauth/token` |
| MCP transport | Streamable HTTP at `https://mcp.canva.com/mcp` |
| Default scopes | `design:meta:read design:content:read asset:read brandtemplate:meta:read folder:read profile:read comment:read` |
| Sync schedule | daily |
| Tools | dynamic — discovered via MCP `tools/list` at install time and cached in `Integration.meta['tools']`. `call(tool, params)` proxies to MCP `tools/call`, so any new server-side tool is callable without code changes. |

Implementation notes:
- `apps/connectors/canva/oauth.py` is the only place that knows about
  PKCE — the view layer generates the verifier/challenge per install,
  stashes the verifier in the session and feeds it to `exchange_code`.
- `apps/connectors/canva/client.py` runs the async `mcp` SDK inside a
  short `asyncio.run()` per call so Celery sync tasks can use it.
- Sync (`sync.py`) probes a small set of conventional read tools
  (`users/me`, `designs/list`, `brand-templates/list`, `folders/list`).
  When a tool is missing or errors out the field is recorded as `null`
  rather than failing the whole snapshot.

### Trello (`apps.connectors.trello`)

| | |
|---|---|
| Auth | API key + token (paste in setup wizard) |
| Base URL | `https://api.trello.com/1` |
| Token source | `https://trello.com/app-key` → "Token" link |
| Sync schedule | every 2 h |
| Snapshot metrics | `boards` (per-board cards + actions), aggregate `cards` (total/open/closed/overdue/completed), aggregate `actions` (volume + by_type + active members) |
| Tools | `me`, `boards.list`, `lists.list`, `cards.list`, `actions.list` |

Setup: `/integrations/trello/setup/` → user pastes API key + token; the
wizard calls `/members/me` to validate before activating.

### Pipedrive (`apps.connectors.pipedrive`)

| | |
|---|---|
| Auth | OAuth 2.0 (3-legged) with refresh tokens (`PIPEDRIVE_CLIENT_ID`/`SECRET`) |
| Authorize URL | `https://oauth.pipedrive.com/oauth/authorize` |
| Token URL | `https://oauth.pipedrive.com/oauth/token` |
| API base | `<api_domain>/v1` — `api_domain` is per-account, returned at OAuth time |
| Default scopes | `deals:read contacts:read users:read activities:read` |
| Sync schedule | every 2 h |
| Snapshot metrics | `pipelines`, `stages`, `deals` (status / stage / value), `persons.total`, `activities` (volume + done/open) |
| Tools | `pipelines.list`, `stages.list`, `users.list`, `deals.list`, `persons.list`, `activities.list` |

The HTTP client refreshes the access token on a 401 and retries the call
once. Refreshed credentials are persisted back into `Credential.encrypted_tokens`.

## Adding a new connector

1. Scaffold `apps/connectors/<name>/` with the file layout above.
2. Implement `MCPIntegration` (auth flow + tool dispatcher).
3. Register the app in `TENANT_APPS` and the URL include in `config/urls.py`.
4. Add the integration to `apps/data_access/mcp/registry.py`.
5. Add the provider constant + label to `Integration.PROVIDER_CHOICES`.
6. Add a Beat entry to `CELERY_BEAT_SCHEDULE` for `connectors.<name>.dispatch`.
7. Document under "Existing connectors" above and append any new env vars
   to `.env.example`.
