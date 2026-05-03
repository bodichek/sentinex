# TODO / Backlog

Persistent backlog of work that's been scoped but deliberately deferred.
Items live here so they're not lost in chat history. Each entry has a
short rationale + rough size estimate.

## Up next (not yet started)

### 1. Seed dev fixtures with mock `DataSnapshot` rows
**Size:** ~30 min · **Why:** so the dashboard / chat agent has data to
show even when the tenant has no real API keys yet. One management
command (`manage.py seed_demo_snapshots`) that inserts plausible rows
for `pipedrive`, `smartemailing`, `trello` — the unified insight
functions then light up all six dashboard cards without any external
calls. Unblocks UI testing on bare environments.

### 2. RAG expansion to Notion / Dropbox / OneDrive
**Size:** 1–1.5 days · **Why:** Knowledge specialist currently only
sees Google Workspace content (via DWD). Architectural decision was
already taken: extend `WorkspaceDocument.SOURCE_CHOICES` with
`notion`, `dropbox`, `onedrive` and write a small per-source ingester
that pulls metadata + text into the existing `WorkspaceDocument` +
`KnowledgeChunk` pipeline. Chunker / embedder / search are
source-agnostic so they need no changes.

### 3. Streaming chat (HTMX SSE)
**Size:** 1 day · **Why:** today the chat does a full POST → page
reload after the orchestrator finishes (can be 5–15s with multiple
specialists + tool-use loops). HTMX server-sent-events would stream
tokens as they arrive, plus stream specialist progress markers
(`StrategicSpecialist analyzing...`). Big perceived-latency win.

### 4. Per-tenant Service Account for Workspace DWD
**Size:** 2 days · **Why:** security followup from the original code
review. Today the Workspace DWD service-account JSON lives globally
in `.env`; one Sentinex deployment can only serve one Google Workspace
domain. Refactor: store the SA JSON encrypted per-tenant in
`Credential.encrypted_tokens` so each tenant brings its own. Keep the
`_validate_subject_domain` cross-tenant guard in place.

### 5. Production polish (group B from earlier roadmap)
**Size:** 2–3 weeks · **Why:** before opening up to first real users.
Bundle of:
- Hetzner deploy with zero-downtime reload (two app containers + Nginx upstream switch).
- Sentry release tagging on each deploy.
- MFA (TOTP) on top of allauth.
- Invitation flow + role management UI (decorator `require_admin`
  already exists, just no UI to assign roles).
- `TenantBudget` UI + alerts at 80 % / 100 %.
- Onboarding flow for new tenants (replacing `bootstrap_dev.py`).

## Parked (waiting on external)

### Symfio
Beta API only by request. Wait for vendor access — see
`docs/CONNECTORS.md` § Roadmap.

### Editee
No public API located during research. Decide later whether to
contact the vendor or drop the connector idea entirely.

## Recently done (for context — full history in git log)

- ✅ A (insight unification + 6 dashboard cards across CRM / ESP / PM
  sources, glass-style restyle).
- ✅ C (smoke tests for all 14 new connectors + registry-level
  invariants).
- ✅ Agent tool-use loop (`complete_with_tools`) + per-specialist
  opt-in via `tool_names`; Strategic, Finance, People, Ops use it.
  Knowledge keeps its own RAG flow.
- ✅ Chat UI: persist tool-call traces into `Message.metadata`,
  expandable per-specialist trace below every assistant bubble.
- ✅ People + Ops hybrid mode (tools first, then strict JSON verdict).
- ✅ Connector setup retry: persisted `last_setup` banner with ISO
  timestamp, non-secret echo, shared `reset_setup` endpoint.
- ✅ `bootstrap_dev.py` for one-shot tenant + admin user setup.

## Conventions

- Each item should land as **one logical commit** with the relevant
  `docs/` file updated in the same commit (per CLAUDE.md
  Documentation Maintenance rule).
- Move items to "Recently done" when the commit lands on `main`; they
  age out over time but don't delete the line until the next major
  refactor — useful for context when revisiting older decisions.
- Symfio + Editee stay in **Parked** until the vendor situation
  changes; don't scope them in unless asked.
