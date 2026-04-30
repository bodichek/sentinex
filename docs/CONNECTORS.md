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

## Group A/B/C connectors — shipped 2026-04

The following 14 providers were added in a single batch alongside the
existing Slack, SmartEmailing, Pipedrive, Canva, Trello and Workspace
(per-user + DWD) connectors.

### Group A — official MCP transport (`mcp` Python SDK + Streamable HTTP)

| Provider | Auth | MCP endpoint | Tools | Sync |
|---|---|---|---|---|
| **Notion** (`apps.connectors.notion`) | OAuth 2.0 | `https://mcp.notion.com/mcp` | dynamic (`tools/list` cached on install in `Integration.meta`) | daily |
| **Dropbox** (`apps.connectors.dropbox`) | OAuth 2.1 + PKCE | `https://mcp.dropbox.com/mcp` | dynamic | daily |

Both follow the Canva pattern: `oauth.py` handles the OAuth handshake,
`client.py` opens a per-call `streamablehttp_client` session with
`Authorization: Bearer <access_token>`, and `integration.py` exposes a
generic `tools/call` proxy so newly-added server tools work without
code changes.

### Group B — REST + OAuth 2.0 (no public MCP yet)

| Provider | Auth | API base | Snapshot metrics | Sync |
|---|---|---|---|---|
| **Microsoft 365** | OAuth 2.0 v2 + `offline_access` | `https://graph.microsoft.com/v1.0` | mail (unread + top senders), calendar (upcoming), OneDrive root, joined Teams | every 2 h |
| **Salesforce** | OAuth 2.0 web-server flow + per-org `instance_url` | `<instance>/services/data/v60.0` | accounts, opportunities (by stage / status / value), leads, users | every 2 h |
| **HubSpot** | OAuth 2.0 | `https://api.hubapi.com` | contacts, companies, deals (by stage / status / amount), pipelines, tickets | every 2 h |
| **Jira** | OAuth 2.0 3LO — discovers `cloudId` via `accessible-resources` | `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3` | projects, recent / open / done issue counts, JQL search | every 2 h |
| **Asana** | OAuth 2.0 + refresh | `https://app.asana.com/api/1.0` | workspaces, projects, tasks (open / completed / overdue) | every 2 h |
| **Basecamp** | OAuth 2.0 (37signals Launchpad) — discovers `account_id` | `https://3.basecampapi.com/{account_id}` | projects (active vs all), todolists, messages | every 6 h |
| **Mailchimp** | OAuth 2.0 — DC discovered via `/oauth2/metadata` | `https://{dc}.api.mailchimp.com/3.0` | audience, campaigns (open rate, CTR) | daily |
| **Calendly** | OAuth 2.0 (Basic on token endpoint) | `https://api.calendly.com` | event types, scheduled events (upcoming + by status) | daily |

Token refresh is automatic on 401 with one retry; refreshed tokens are
persisted back into `Credential.encrypted_tokens`.

### Group C — paste-key flow (Czech tools)

| Provider | Auth | Docs | Snapshot metrics | Sync |
|---|---|---|---|---|
| **Raynet CRM** | HTTP Basic (`instance` + `username` + `api_key`) | [api.doc](https://app.raynetcrm.com/api/doc/index-en.html) | companies count, leads count, business cases (by state, value), invoices | every 6 h |
| **Caflou** | Bearer token | [docs.caflou.cz](https://docs.caflou.cz/integrace/api) | companies / projects / tasks / invoices / timesheets counts | daily |
| **Ecomail** | `key` header | [docs.ecomail.cz](https://docs.ecomail.cz/) | audience (lists, total subscribers), campaigns (open rate, CTR) | daily |
| **FAPI** | HTTP Basic (e-mail + api_key) | [web.fapi.cz/api-doc](https://web.fapi.cz/api-doc/) | invoices (by status + total / paid amount), clients, vouchers | every 6 h |

All Group C connectors use a 3-step Google-consent-style wizard at
`/integrations/<provider>/setup/`: (1) where to find the credential,
(2) how to generate it, (3) paste form — the wizard pings the upstream
API before activating the integration.

## Roadmap — planned connectors

Verified during research (2026‑04). Status legend: ✅ shipped · 🟡 planned ·
🚧 needs OAuth app registration · ❓ blocked / awaiting vendor.

### Group A — official MCP transport (use the `mcp` Python SDK like Canva)

| Provider | Auth | Endpoint / source | Sentinex use |
|---|---|---|---|
| 🟡 Notion | OAuth 2.0 | Official Notion MCP server | search, pages, databases — feeds Knowledge RAG alongside Workspace DWD |
| 🟡 HubSpot | OAuth 2.0 | Official HubSpot MCP (Breeze MCP Client) | contacts, deals, pipelines, tickets — alternate CRM to Pipedrive |
| 🟡 Jira (Atlassian) | OAuth 2.0 (3LO) | Official Atlassian Remote MCP | issues, sprints, JQL search — tech-team velocity |
| 🟡 Dropbox | OAuth 2.0 + PKCE | Official Dropbox Remote MCP | files, search — alternate Knowledge RAG source |

### Group B — REST + OAuth 2.0, no public MCP yet

| Provider | Auth | API base | Sentinex use |
|---|---|---|---|
| 🟡 Microsoft 365 (mail + Teams + OneDrive + Calendar) | OAuth 2.0 (Microsoft Graph) | `https://graph.microsoft.com/v1.0` | one connector covers Outlook, Teams chat/meetings, OneDrive, Calendar — MS-shop alternative to Workspace DWD. Community `ms-365-mcp-server` exists; we go REST for stability. |
| 🟡 Salesforce | OAuth 2.0 (web server flow) + per-org instance URL | `<instance>/services/data/vXX.X/` | accounts, opportunities, leads — enterprise CRM |
| 🟡 Asana | OAuth 2.0 or PAT | `https://app.asana.com/api/1.0/` | tasks, projects, throughput |
| 🟡 Basecamp | OAuth 2.0 (37signals) | `https://3.basecampapi.com/{account_id}/` | todos, messages, schedule |
| 🟡 Mailchimp | OAuth 2.0 *or* API key (data-center prefix) | `https://{dc}.api.mailchimp.com/3.0/` | audience growth, campaign engagement |
| 🟡 Calendly | OAuth 2.0 or PAT | `https://api.calendly.com/` (v2) | scheduling load, no-show rate |

### Group C — Czech tools (paste-key flow, like SmartEmailing / Trello)

| Provider | Auth | API docs | Sentinex use |
|---|---|---|---|
| 🟡 Raynet CRM | API key | `https://app.raynetcrm.com/api/doc/index-en.html` | Czech CRM — accounts, deals, activities |
| 🟡 Caflou | API key (Bearer) | Postman: `https://documenter.getpostman.com/view/4786951/RWMFrTQC` | Czech all-in-one — clients, projects, invoices |
| 🟡 Ecomail | API key | `https://docs.ecomail.cz/` (v2) | Czech e-mail marketing alternative to SmartEmailing |
| 🟡 FAPI | API key + email | `https://web.fapi.cz/api-doc/` | Czech invoicing + affiliate — revenue signal for the finance specialist |

### Architectural decisions taken during planning

- **Microsoft 365 + Teams + OneDrive + Outlook = one connector app**
  (`apps/connectors/microsoft365/`) over Microsoft Graph. Single OAuth
  flow, single refresh token, dispatcher exposes
  `mail.*`, `teams.*`, `onedrive.*`, `calendar.*` tools.
- **CRM insight unification.** `get_pipeline_velocity` will be widened
  to read the most recent snapshot whose `source` is in
  `{pipedrive, hubspot, salesforce, raynet}` so dashboards stay neutral
  to which CRM the tenant uses.
- **Marketing insight unification.** `get_marketing_funnel` will be
  widened to read snapshots from `{smartemailing, ecomail, mailchimp}`
  for the same reason.
- **Knowledge RAG sources.** Notion, Dropbox and OneDrive will plug
  into the existing `WorkspaceDocument` + `KnowledgeChunk` pipeline as
  additional `source` values; the chunker / embedder / search layer
  does not need changes.

### Suggested delivery order

| Sprint | Connectors | Rationale |
|---|---|---|
| W1 | Microsoft 365 (Graph: mail + Teams + OneDrive + Calendar) | highest ROI for MS-shop tenants, expands Knowledge RAG to OneDrive |
| W2 | Notion (MCP) + Asana | broadens RAG coverage + project/PM signal |
| W3 | HubSpot (MCP) + Jira (MCP) | CRM + tech-team velocity via official MCP servers |
| W4 | Salesforce + Calendly | enterprise CRM + scheduling load metrics |
| W5 | Mailchimp + Basecamp + Dropbox (MCP) | rounds out marketing / PM / file sources |
| W6 | Raynet + Caflou + Ecomail + FAPI | Czech all-in-one, paste-key — ~1 day each |

### Pre-flight checklist (do before W1 starts)

For every Group A & B connector we need a **platform-level OAuth app**
registered in the vendor's developer portal. The `client_id` /
`client_secret` go in `.env` (one app per provider, shared across
tenants). Per-tenant tokens stay in `Credential.encrypted_tokens`.

| Provider | Where to register |
|---|---|
| Microsoft 365 | Azure portal → App registrations |
| Notion | notion.so/my-integrations |
| HubSpot | developers.hubspot.com/apps |
| Atlassian / Jira | developer.atlassian.com → OAuth 2.0 (3LO) apps |
| Dropbox | dropbox.com/developers/apps |
| Salesforce | Setup → App Manager → New Connected App |
| Asana | app.asana.com/0/my-apps |
| Basecamp | launchpad.37signals.com/integrations |
| Mailchimp | admin.mailchimp.com/account/oauth2 |
| Calendly | calendly.com/integrations/api_webhooks |

Czech connectors (Group C) need no app registration — each tenant's
admin pastes their own API key in the setup wizard.

## Adding a new connector

1. Scaffold `apps/connectors/<name>/` with the file layout above.
2. Implement `MCPIntegration` (auth flow + tool dispatcher).
3. Register the app in `TENANT_APPS` and the URL include in `config/urls.py`.
4. Add the integration to `apps/data_access/mcp/registry.py`.
5. Add the provider constant + label to `Integration.PROVIDER_CHOICES`.
6. Add a Beat entry to `CELERY_BEAT_SCHEDULE` for `connectors.<name>.dispatch`.
7. Document under "Existing connectors" above and append any new env vars
   to `.env.example`.
