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

### 5. Three-layer extraction pipeline for external data
**Size:** 3–5 days · **Why:** today the data pipeline is two-tier:
**(L1)** aggregated `DataSnapshot` per connector (numbers only — totals,
by_status, by_stage), **(L2)** vectorised knowledge index but **only
for Google Workspace via DWD** (`WorkspaceDocument` + `KnowledgeChunk`
with pgvector). CRM / ESP / PM connectors discard raw record payloads
after rolling them up into the snapshot, so the agent can answer
"how many deals are won" but **not** "which deal with ACME closed last
week". No automatic classification or tagging beyond `source` +
`mime_type`.

**Target architecture — three layers:**

```
┌─ L1 — raw record ────┐ ┌─ L2 — extracted facts ──┐ ┌─ L3 — aggregates ─┐
│ ExternalRecord row   │→│ entities, relationships,│→│ DataSnapshot      │
│ (full payload, vec)  │ │ classification tags     │ │ (existing model)  │
└──────────────────────┘ └─────────────────────────┘ └───────────────────┘
       ↓                            ↓                          ↓
  pgvector RAG              structured queries          dashboard cards
  (Knowledge spec)          (insight functions+)        (existing)
```

**Concrete deliverables:**

1. **New `ExternalRecord` model** under `apps/data_access/`:
   `source`, `external_id`, `record_type` (deal / contact / message /
   card / …), `payload jsonb` (full API response), `embedding
   vector(1536)`, `metadata jsonb`, `tags[]`, `created_at`,
   `updated_at`, `last_synced_at`. Replaces the current ad-hoc
   per-source collection pattern.
2. **Refactor each connector's `sync.py`** to upsert `ExternalRecord`
   rows alongside writing the `DataSnapshot`. The snapshot becomes a
   *materialised view* over the records rather than the only output.
3. **L2 extraction step** — async Celery task triggered on record
   upsert: invoke Haiku with `complete_with_tools` (tools like
   `tag_record`, `extract_entities`, `link_to_existing`) to populate
   `tags`, `metadata` and a small entity graph.
4. **Embed every record** into pgvector (same chunker / embedding
   gateway as Workspace knowledge). Knowledge specialist's tool set
   then searches across all sources uniformly — not just Workspace.
5. **Insight functions stay** — they keep reading `DataSnapshot`,
   so the dashboard contract doesn't change. Slowly migrate them to
   read from `ExternalRecord` directly when it pays off (e.g. show
   the deal names behind "12 won this month").

**Pre-flight check before starting:**

Run a test pass on real tenant data first (item #1 below — seed
fixtures or, better, a real connector). If 80 % of agent queries are
satisfied by aggregated metrics alone, this whole tier is yagni and
can stay parked. Only build it when a real query comes back as
"agent answered the wrong thing because it only saw totals".

ADR (Architecture Decision Record) goes in
`docs/adr/0001-three-layer-extraction.md` once we commit to it.

### 6. Production polish (group B from earlier roadmap)
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
