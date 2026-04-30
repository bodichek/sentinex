# Google Workspace — Domain-Wide Delegation (DWD) Connector

A single connector that gives Sentinex read-only access to **everything** a
Google Workspace company has: Gmail, Drive, Calendar, Docs, Sheets, Slides,
Directory, Audit logs, Tasks, Keep, Chat. No per-user OAuth screens — one
admin authorises, the connector impersonates each user as needed.

This document covers what to set up on Google's side, what to configure in
Sentinex, and how the ingestion pipeline turns those raw artifacts into a
RAG-ready knowledge index.

---

## 1. One-time setup on Google's side (~20 min)

### 1.1 Service Account

1. Open <https://console.cloud.google.com>.
2. Create or select a project (e.g. `sentinex-prod`).
3. **APIs & Services → Library** — enable each of:
   - Gmail API
   - Google Drive API
   - Google Calendar API
   - Google Docs API
   - Google Sheets API
   - Google Slides API
   - Admin SDK API
   - People API
   - Google Tasks API
   - Google Chat API (optional)
4. **IAM & Admin → Service Accounts → Create**.
   - Name: `sentinex-workspace-connector`.
   - After creating: **Keys → Add Key → JSON** — downloads
     `sentinex-…-abc123.json`. Store it securely; the next step needs the
     **Unique ID** (numeric `client_id`) from the same screen.

### 1.2 Authorise Domain-Wide Delegation

1. Open <https://admin.google.com> as a Workspace **super-admin**.
2. **Security → Access and data control → API controls → Manage Domain-Wide
   Delegation → Add new**.
3. **Client ID:** the SA's Unique ID from step 1.4.
4. **OAuth scopes:** paste the list from the Sentinex
   `/integrations/google_workspace_dwd/setup/` page (also reproduced below).
   The list is comma-separated.
5. Click **Authorize**.

### 1.3 Scopes (read-only, no scope is "write")

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/drive.metadata.readonly
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/calendar.events.readonly
https://www.googleapis.com/auth/documents.readonly
https://www.googleapis.com/auth/spreadsheets.readonly
https://www.googleapis.com/auth/presentations.readonly
https://www.googleapis.com/auth/contacts.readonly
https://www.googleapis.com/auth/contacts.other.readonly
https://www.googleapis.com/auth/directory.readonly
https://www.googleapis.com/auth/admin.directory.user.readonly
https://www.googleapis.com/auth/admin.directory.group.readonly
https://www.googleapis.com/auth/admin.directory.orgunit.readonly
https://www.googleapis.com/auth/admin.reports.audit.readonly
https://www.googleapis.com/auth/admin.reports.usage.readonly
https://www.googleapis.com/auth/tasks.readonly
https://www.googleapis.com/auth/keep.readonly
https://www.googleapis.com/auth/chat.messages.readonly
https://www.googleapis.com/auth/chat.spaces.readonly
https://www.googleapis.com/auth/chat.memberships.readonly
```

You can authorise a **subset** at first (e.g. only `directory.readonly` +
`drive.readonly`) and broaden later. The full list is the upper bound.

---

## 2. Configure Sentinex

Set these in `.env`:

```bash
# Path to the JSON key file on disk (preferred)
GOOGLE_WORKSPACE_SA_JSON_PATH=/var/secrets/sentinex-sa.json

# OR inline JSON (less secure; useful in container envs)
# GOOGLE_WORKSPACE_SA_JSON={"type":"service_account",...}

GOOGLE_WORKSPACE_DOMAIN=acme.cz
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@acme.cz

# Embeddings — required for RAG search. Stub mode is fine for dev.
OPENAI_API_KEY=sk-...
KNOWLEDGE_STUB_MODE=False
```

Restart the app + Celery worker + Celery Beat. Open
`/integrations/google_workspace_dwd/setup/` — three green dots = ready.

---

## 3. First ingest

Either the UI or the management command:

```bash
# CLI (per tenant)
python manage.py workspace_ingest --tenant=public --mode=full

# Smoke-test the search
python manage.py knowledge_search --tenant=public --query="cenotvorba 2026"
```

### What happens

```
files.list (corpora=domain)
  → WorkspaceDocument rows (one per Drive file, mime detection)
  → ingest_drive_file Celery task fan-out
       → extract_*  (per-MIME extractor returns plain text)
       → chunk_text (token-aware, ~800 tokens, 100-token overlap)
       → embed_texts (OpenAI text-embedding-3-small, 1536-dim)
       → INSERT INTO data_access_knowledgechunk (raw SQL, pgvector type)
  → IngestionCursor stamped with `startPageToken`
```

After full sync, **Celery Beat** runs `knowledge_incremental_dispatch` every
5 minutes — picks up Drive Changes since the last cursor and re-indexes only
what changed.

---

## 4. How agents use the index

`apps/agents/specialists/knowledge.py` (`KnowledgeSpecialist`) wraps the
search + LLM call. It is registered in the specialist `REGISTRY`, so the
orchestrator can route a query to it directly.

The specialist:
1. Calls `search_company_knowledge(query)` (an Insight Function).
2. Top-K chunks become numbered citations in the user prompt.
3. The system prompt forces grounded answers — no fabrication, citations
   required, "I don't know" if context is insufficient.

For non-agent UI flows there is also a plain semantic search page at
`/knowledge/`.

---

## 5. Cost & scale guardrails

| Knob | Default | Where |
|---|---|---|
| Max file size for extraction | 20 MB | `KNOWLEDGE_MAX_FILE_BYTES` |
| Chunk size | 800 tokens | `KNOWLEDGE_CHUNK_SIZE_TOKENS` |
| Chunk overlap | 100 tokens | `KNOWLEDGE_CHUNK_OVERLAP_TOKENS` |
| Embedding model | text-embedding-3-small | `KNOWLEDGE_EMBEDDING_MODEL` |
| Vector dim | 1536 | `KNOWLEDGE_EMBEDDING_DIMENSIONS` |
| Stub mode (no API) | False | `KNOWLEDGE_STUB_MODE` |
| MCP rate limit | 60/min/integration | `gateway.RATE_LIMIT_PER_MINUTE` |

**Rough cost** for a 50-employee company with ~200 k Drive files (~1 GB
text) — approx **$5 one-time embedding cost**, ~600 MB pgvector storage,
incremental drift below $1/month.

---

## 5b. Cross-tenant impersonation guard

The connector accepts a `subject` email when delegating credentials
(`gmail_client(user_email)`, `calendar_client(user_email)`, …). Without a
domain check, any caller could ask the SA to impersonate
`ceo@some-other-company.com` — a cross-tenant escalation.

`get_credentials()` now validates that every `subject` ends with
`@<GOOGLE_WORKSPACE_DOMAIN>` and raises `RuntimeError` otherwise. As a
consequence:

- `GOOGLE_WORKSPACE_DOMAIN` is **required**; missing value → all DWD calls fail.
- A tenant cannot ingest mailboxes or calendars belonging to users outside
  the configured Workspace domain, even if it knows their email addresses.
- The current MVP supports a single Workspace domain platform-wide. Per-tenant
  Service Accounts (one Workspace per Sentinex tenant) is a follow-up — the
  domain check stays valid in that future model, scoped per `Credential`.

---

## 6. Privacy & compliance

The connector has read access to every employee mailbox and Drive file.
Before turning on Gmail or Drive scopes:

- Document a DPIA (GDPR Art. 35) for the customer organisation.
- Inform employees per Art. 13 (purpose, retention, lawful basis).
- Default to the **directory + calendar + audit-log** scopes only; add
  Gmail/Drive when there's a specific use case.
- All MCP calls are audit-logged (`MCPCall` model). `WorkspaceDocument`
  carries the owner's email so you can scope queries with `owner_email=`.

Sentinex never stores SA private keys in the database. Keys live on disk
or in environment variables managed by the host platform.

---

## 7. Files added by the DWD feature

```
apps/data_access/
  mcp/integrations/google_workspace_dwd.py    # SA auth + client factories
  mcp/registry.py                             # default_gateway() w/ DWD
  knowledge/                                  # ingestion pipeline
    discovery.py, chunker.py, embedder.py,
    indexer.py, search.py, tasks.py, views.py, urls.py
    extractors/                               # per-MIME handlers
  insight_functions/knowledge.py              # search_company_knowledge
  sync/google_workspace_dwd.py                # directory/calendar/audit syncs
  management/commands/workspace_ingest.py
  management/commands/knowledge_search.py
  migrations/0004_workspace_document_and_cursor.py
  migrations/0005_knowledge_chunk.py          # pgvector raw SQL

apps/agents/specialists/knowledge.py          # RAG specialist
apps/agents/prompts/knowledge_specialist.yaml

templates/integrations/workspace_dwd_setup.html
templates/integrations/workspace_dwd_dashboard.html
templates/knowledge/search.html
templates/knowledge/_results.html
```
