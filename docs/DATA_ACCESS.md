# Data Access Layer

The Data Access Layer is Sentinex's primary competitive moat. This document describes its design and how to extend it.

## Purpose

The Data Access Layer (DAL) provides a unified, typed, testable interface for agents and addons to retrieve information about an organization. It abstracts over raw data sources (APIs, databases, MCP servers) and exposes business-relevant functions.

Three main components:
1. **Insight Functions**: pure Python functions encoding business methodology
2. **MCP Gateway**: unified interface to MCP servers
3. **Direct API Clients**: custom clients for systems without MCP support

## Insight Functions

### What They Are

Pure Python functions that answer business-level questions about an organization. Typed inputs, typed outputs, framework-agnostic, unit-tested.

### Philosophy

Insight Functions encode **methodology** (Scaling Up, EOS, OKR, custom) as executable code. Agents and addons consume these functions without knowing the underlying data source.

Key properties:
- **Pure**: no side effects, deterministic given same inputs
- **Typed**: inputs and outputs are typed (Pydantic or dataclasses)
- **Cached**: results cached in Redis where appropriate
- **Composable**: functions can call other functions
- **Framework-agnostic**: names and outputs don't reference specific methodologies

### Examples

```python
# apps/data_access/insight_functions/strategic.py

from dataclasses import dataclass
from datetime import date

from apps.core.models import Organization

@dataclass
class WeeklyMetrics:
    period_start: date
    period_end: date
    revenue: float | None
    new_customers: int | None
    key_indicators: dict[str, float]
    data_quality: str  # "high", "partial", "missing"

def get_weekly_metrics(org: Organization) -> WeeklyMetrics:
    """Compute key weekly metrics for an organization.

    Aggregates data from connected sources. Returns data_quality="partial"
    if some sources are disconnected, "missing" if no usable data.
    """
    ...
```

### Function Categories

**Strategic**
- `get_weekly_metrics(org) -> WeeklyMetrics`
- `get_quarterly_priorities_status(org, quarter) -> list[Priority]`
- `get_recent_anomalies(org, period) -> list[Anomaly]`
- `get_decision_history(org, topic) -> list[Decision]`
- `get_strategic_risks(org, horizon) -> list[Risk]`

**Finance**
- `get_cash_runway_projection(org, months) -> CashRunway`
- `get_margin_trends(org, period) -> MarginTrends`
- `get_unit_economics(org) -> UnitEconomics`
- `get_cashflow_snapshot(org) -> CashflowSnapshot`

**People**
- `get_team_health_signals(org, period) -> TeamHealth`
- `get_accountability_gaps(org) -> list[Gap]`
- `get_turnover_risk(org) -> TurnoverRisk`
- `get_team_activity_summary(org, period) -> TeamActivity`

**Customer**
- `get_pipeline_velocity(org) -> PipelineVelocity`
- `get_deal_risk_signals(org) -> list[DealRisk]`
- `get_customer_health_score(org, segment) -> HealthScore`
- `get_churn_indicators(org) -> list[ChurnIndicator]`

**Operations**
- `get_upcoming_commitments(org) -> list[Commitment]`
- `get_project_status(org, project_id) -> ProjectStatus`
- `get_bottleneck_signals(org) -> list[Bottleneck]`

**Knowledge (RAG over Workspace)**
- `search_company_knowledge(query, top_k=8, source=None, owner_email=None)
  -> KnowledgeAnswerContext`

  Semantic top-K search over indexed Drive/Gmail/Calendar artifacts. Returns
  both structured hits (for UI rendering) and a pre-formatted prompt block
  with citations (drop-in for LLM system prompts). Backed by the pgvector
  table `data_access_knowledgechunk` and the OpenAI embedding model
  configured via `KNOWLEDGE_EMBEDDING_MODEL`. See
  `docs/GOOGLE_WORKSPACE_DWD.md` for the full pipeline.

### Writing a New Insight Function

#### 1. Define the output type

```python
# apps/data_access/insight_functions/types/finance.py

from dataclasses import dataclass
from datetime import date

@dataclass
class CashRunway:
    calculation_date: date
    current_cash: float
    monthly_burn: float
    months_remaining: float
    projection_confidence: str  # "high", "medium", "low"
    assumptions: list[str]
```

#### 2. Implement the function

```python
# apps/data_access/insight_functions/finance.py

from apps.core.models import Organization
from .types.finance import CashRunway

def get_cash_runway_projection(
    org: Organization,
    months: int = 12,
) -> CashRunway:
    """Project cash runway based on current burn rate.

    Args:
        org: The organization.
        months: How many months to project.

    Returns:
        CashRunway with current state and projection.

    Raises:
        InsufficientData: If financial data is not available.
    """
    # Fetch data from synced sources
    # Apply methodology
    # Return typed result
    ...
```

#### 3. Register in index

```python
# apps/data_access/insight_functions/__init__.py

from .strategic import get_weekly_metrics, get_quarterly_priorities_status
from .finance import get_cash_runway_projection, get_margin_trends

__all__ = [
    "get_weekly_metrics",
    "get_quarterly_priorities_status",
    "get_cash_runway_projection",
    "get_margin_trends",
]

# Registry for dynamic discovery
INSIGHT_FUNCTIONS = {
    "get_weekly_metrics": get_weekly_metrics,
    "get_quarterly_priorities_status": get_quarterly_priorities_status,
    "get_cash_runway_projection": get_cash_runway_projection,
    "get_margin_trends": get_margin_trends,
}
```

#### 4. Write tests

```python
# apps/data_access/insight_functions/tests/test_finance.py

import pytest
from datetime import date
from apps.data_access.insight_functions import get_cash_runway_projection

@pytest.mark.django_db
def test_cash_runway_with_complete_data(organization_with_finance_data):
    result = get_cash_runway_projection(organization_with_finance_data)

    assert result.calculation_date == date.today()
    assert result.current_cash > 0
    assert result.monthly_burn > 0
    assert result.months_remaining > 0
    assert result.projection_confidence in ("high", "medium", "low")

@pytest.mark.django_db
def test_cash_runway_with_missing_data(organization_without_finance_data):
    with pytest.raises(InsufficientData):
        get_cash_runway_projection(organization_without_finance_data)
```

#### 5. Caching (optional)

For expensive functions, add Redis caching:

```python
from apps.core.cache import cache_result

@cache_result(ttl=3600, key_prefix="cash_runway")
def get_cash_runway_projection(org: Organization, months: int = 12) -> CashRunway:
    ...
```

Cache key includes tenant and function arguments. Cache invalidation on relevant data sync events.

## MCP Gateway

### Purpose

The MCP Gateway provides a unified interface for interacting with MCP (Model Context Protocol) servers. Agents and addons don't talk to MCP servers directly — they go through the gateway.

### Features

- Per-tenant credential management (encrypted)
- OAuth flow orchestration
- Rate limiting per tenant
- Response caching
- Audit logging
- Error handling and retries
- Token usage tracking

### Supported MCP Servers (MVP)

**Google Workspace — per-user OAuth** (`google_workspace`)
- 3-legged OAuth, each user connects their own account.
- Backed by the official Anthropic Google Workspace MCP server when
  `SENTINEX_MCP_GW_URL` is set; otherwise calls return stubs.
- Best for early pilots / read-only on a single user mailbox.

**Google Workspace — Domain-Wide Delegation** (`google_workspace_dwd`)
- Service Account + DWD: one-time admin authorisation, no per-user
  consent screens.
- Direct Google API client (`google-api-python-client`) — no MCP server
  required for this provider.
- Read scope across the entire Workspace: Gmail, Drive, Calendar, Docs,
  Sheets, Slides, Directory, Reports/audit, Tasks, Keep, Chat.
- Implementation: `apps/data_access/mcp/integrations/google_workspace_dwd.py`
- See `docs/GOOGLE_WORKSPACE_DWD.md` for full setup, scopes, cost model
  and privacy notes.

**Slack** (`slack`)
- Bot-token integration via `slack-sdk`.
- Channel listing, message search, user metadata.

The default registry that knows about all three providers is in
`apps/data_access/mcp/registry.py` — call `default_gateway()` everywhere
instead of constructing `MCPGateway({...})` ad-hoc.

### Adding a New MCP Integration

#### 1. Create integration config

```python
# apps/data_access/mcp/integrations/microsoft365.py

from apps.data_access.mcp.base import MCPIntegration

class Microsoft365Integration(MCPIntegration):
    name = "microsoft365"
    display_name = "Microsoft 365"
    mcp_server_url = "mcp://..."  # or npx command

    oauth_config = {
        "provider": "microsoft",
        "scopes": ["Mail.Read", "Calendars.Read", "Files.Read"],
        "redirect_uri": "/integrations/microsoft365/callback",
    }

    def get_tools(self):
        return ["read_email", "list_events", "search_files"]
```

#### 2. Register OAuth provider

Add OAuth credentials to settings:

```python
# config/settings/base.py

SOCIAL_AUTH_PROVIDERS = {
    "microsoft": {
        "client_id": env("MICROSOFT_CLIENT_ID"),
        "client_secret": env("MICROSOFT_CLIENT_SECRET"),
    },
}
```

#### 3. Create UI for connection

Users connect their integration in tenant settings:

```python
# apps/core/views/integrations.py

class ConnectMicrosoft365View(LoginRequiredMixin, View):
    def get(self, request):
        return redirect(
            build_oauth_url("microsoft365", request.user.tenant)
        )
```

#### 4. Handle callback

Store encrypted credentials:

```python
class Microsoft365CallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        tokens = exchange_code(code)

        Credential.objects.update_or_create(
            tenant=request.tenant,
            integration="microsoft365",
            defaults={"tokens": encrypt(tokens)},
        )

        return redirect("integrations:list")
```

#### 5. Use in agents

Agents access MCP tools via gateway:

```python
from apps.data_access.mcp.gateway import MCPGateway

gateway = MCPGateway(tenant=org.tenant)
result = gateway.call(
    integration="microsoft365",
    tool="read_email",
    params={"filter": "last_week"},
)
```

## Direct API Clients

For systems without MCP support.

### Structure

```
apps/data_access/api_clients/
├── __init__.py
├── base.py                 # BaseAPIClient abstract class
├── exceptions.py           # Common exceptions
├── pohoda_client.py        # Future: Czech accounting
├── abra_client.py          # Future: Czech ERP
└── helios_client.py        # Future: Czech ERP
```

### Base Class

```python
# apps/data_access/api_clients/base.py

from abc import ABC, abstractmethod

class BaseAPIClient(ABC):
    def __init__(self, credentials):
        self.credentials = credentials
        self.session = self._build_session()

    @abstractmethod
    def health_check(self) -> bool:
        """Verify connection is working."""
        ...

    def _build_session(self):
        # HTTP session with retries, timeouts, auth
        ...
```

### Implementation Example

```python
# apps/data_access/api_clients/pohoda_client.py

class PohodaClient(BaseAPIClient):
    def health_check(self) -> bool:
        response = self.session.get("/health")
        return response.status_code == 200

    def get_invoices(self, date_from, date_to):
        response = self.session.get(
            "/invoices",
            params={"from": date_from, "to": date_to},
        )
        return [self._parse_invoice(i) for i in response.json()]
```

## Sync Pipelines

Celery workers that periodically fetch data from sources and store metrics.

### Scheduled Syncs

```python
# apps/data_access/sync/tasks.py

from celery import shared_task
from apps.core.models import Organization
from apps.data_access.sync.google_workspace import sync_google_workspace_data

@shared_task
def sync_all_tenants():
    for org in Organization.objects.filter(is_active=True):
        sync_google_workspace_for_org.delay(org.id)

@shared_task
def sync_google_workspace_for_org(org_id):
    org = Organization.objects.get(pk=org_id)
    sync_google_workspace_data(org)
```

### Data Minimization

Sync pipelines store **metrics, not raw data**:

```python
def sync_google_workspace_data(org):
    # Fetch raw emails
    emails = gateway.call(
        integration="google_workspace",
        tool="search_emails",
        params={"period": "last_week"},
    )

    # Compute metrics (no storage of raw email content)
    metrics = {
        "email_count": len(emails),
        "unique_senders": len({e["from"] for e in emails}),
        "avg_response_time_hours": compute_avg_response_time(emails),
        "peak_activity_day": find_peak_day(emails),
    }

    # Store only metrics
    DataSnapshot.objects.create(
        organization=org,
        source="google_workspace",
        period_end=date.today(),
        metrics=metrics,
    )
```

Raw data is not persisted in Sentinex database. Only aggregated metrics.

### Retention Policies

- Raw data: never stored
- Metrics: 24 months rolling
- LLM conversation logs: 12 months
- Audit logs: 36 months (compliance requirement)

## Testing the Data Access Layer

### Unit tests for Insight Functions

Use mock data fixtures:

```python
@pytest.fixture
def org_with_full_data(db):
    org = Organization.objects.create(name="Test")
    DataSnapshot.objects.create(
        organization=org,
        source="finance",
        metrics={"cash": 1000000, "burn": 100000},
    )
    return org

def test_cash_runway_full_data(org_with_full_data):
    result = get_cash_runway_projection(org_with_full_data)
    assert result.months_remaining == 10
```

### Integration tests for MCP Gateway

Use test MCP server or mocked responses:

```python
@pytest.mark.integration
def test_mcp_gateway_google_workspace(mock_mcp_server):
    gateway = MCPGateway(tenant=test_tenant)
    result = gateway.call(
        integration="google_workspace",
        tool="list_calendar_events",
        params={"date": "2026-04-22"},
    )
    assert len(result) > 0
```

## Performance Considerations

- Cache expensive Insight Functions (Redis)
- Batch MCP calls where possible
- Sync pipelines run asynchronously, never in request cycle
- Use `select_related` and `prefetch_related` aggressively
- Monitor slow queries (pg_stat_statements)

## Security

- All credentials encrypted at rest (django-cryptography)
- OAuth tokens refreshed proactively (5-min buffer before expiry)
- MCP calls include tenant filter
- Audit log for all external API calls
- Never log raw response data (PII risk)

## Knowledge Pipeline (RAG over Workspace)

Sentinex turns the customer's entire Google Workspace into a queryable
knowledge index. The pipeline is fully tenant-scoped and runs on top of the
DWD connector described above.

### End-to-end flow

```
discovery   → extraction      → chunking       → embedding         → indexing
files.list    per-MIME           token-aware     OpenAI                pgvector
(domain)      handler            chunker         text-embedding-       (raw SQL +
                                                 3-small               ivfflat idx)
                                                 (1536-dim)
```

Module map (`apps/data_access/knowledge/`):

| File | Responsibility |
|------|----------------|
| `discovery.py` | Paginate `drive.files.list` over the domain; emit start/page tokens for incremental sync. |
| `extractors/base.py` | Registry mapping MIME type → handler returning `ExtractionResult`. |
| `extractors/google_docs.py` | `application/vnd.google-apps.document` via Drive export to `text/plain`. |
| `extractors/google_sheets.py` | `application/vnd.google-apps.spreadsheet` via Sheets API; flat TSV with sheet headers. |
| `extractors/google_slides.py` | `application/vnd.google-apps.presentation` via Slides API; per-slide text runs. |
| `extractors/pdf.py` | `application/pdf` via Drive `get_media` + `pypdf`. |
| `extractors/plain_text.py` | `text/plain`, `text/markdown`, `text/csv`, `text/html`. |
| `extractors/gmail.py` | Gmail message → headers + plain-text body. |
| `chunker.py` | Token-aware chunker (tiktoken `cl100k_base`); paragraph-first, hard-split fallback. |
| `embedder.py` | Thin wrapper that delegates to `apps/agents/embedding_gateway` (Redis cache, retries, cost accounting, structured `sentinex.llm` events, tenant attribution). Enforces dimension match against `KNOWLEDGE_EMBEDDING_DIMENSIONS`. Stub mode preserved for offline dev. |
| `indexer.py` | Orchestrates extract → chunk → embed → upsert into `data_access_knowledgechunk`. |
| `search.py` | Cosine-similarity retrieval; `format_hits_for_prompt` for citation-style RAG. |
| `tasks.py` | Celery: `full_ingest_workspace`, `incremental_ingest_workspace`, per-file `ingest_drive_file`. |
| `views.py` + `urls.py` | `/knowledge/` HTMX live search page. |

### Models

- `WorkspaceDocument` — one row per Drive file / Gmail thread / Calendar
  artifact. Captures source, external_id, title, mime, owner, modified_at,
  size, status (`pending` → `extracted` → `indexed` / `failed` / `skipped`),
  raw extracted text (capped at 1 MB).
- `IngestionCursor` — per-source watermark; for Drive holds the
  `startPageToken` returned by Drive Changes API.
- `KnowledgeChunk` — chunk-level rows with `text`, `token_count`,
  `embedding vector(1536)`, `metadata jsonb`. Created via raw SQL in
  migration `0005_knowledge_chunk` so the `vector` extension can be probed
  first; `Meta.managed = False` keeps Django from emitting standard CREATE
  TABLE.

### Operating it

CLI:

```bash
# Full or incremental
python manage.py workspace_ingest --tenant=acme --mode=full
python manage.py workspace_ingest --tenant=acme --mode=incremental

# Directory / audit one-shots
python manage.py workspace_ingest --tenant=acme --mode=directory --domain=acme.cz
python manage.py workspace_ingest --tenant=acme --mode=audit --days=7

# Smoke-test the index
python manage.py knowledge_search --tenant=acme --query="cenotvorba 2026"
```

UI:

- `/integrations/google_workspace_dwd/setup/` — config status (3 dots).
- `/integrations/google_workspace_dwd/dashboard/` — counts per status,
  cursor info, recent failures, full / incremental buttons.
- `/knowledge/` — HTMX live search page with cited snippets.

Celery Beat (defined in `config/settings/base.py`):

| Task | Schedule | Purpose |
|------|----------|---------|
| `data_access.knowledge_incremental_dispatch` | every 5 min | fan out incremental ingest per active DWD tenant |
| `data_access.workspace_directory_dispatch`   | daily       | refresh employee list / org units |
| `data_access.workspace_audit_dispatch`       | hourly      | pull last-24h login audit |
| `data_access.sync_slack_dispatch`            | every 6 h   | unrelated, listed for completeness |

### Cost model (rough)

For a 50-employee org with ~1 GB indexed text:

| Item | One-off | Recurring |
|------|---------|-----------|
| Embedding (text-embedding-3-small @ $0.02 / 1M tok) | ~$5 | <$1 / month (drift) |
| pgvector storage (~600 MB) | included | included |
| LLM RAG queries (Sonnet, 8 hits × ~600 tok each) | — | ~$0.005 / query |

### Embedding gateway (single chokepoint)

All real OpenAI embedding traffic — both ingest (`indexer.py`) and query
(`search.py`) — flows through `apps/agents/embedding_gateway.embed()`.
That gives RAG the same operational guarantees as LLM completions:

- Exact-match Redis cache keyed on `(model, text)` — duplicate chunks /
  repeated queries become free.
- Tenacity-based retries with exponential backoff.
- Cost accounting in USD via `PRICE_USD_PER_MILLION_TOKENS`.
- Structured `sentinex.llm` JSON event with tenant tag, latency, cache
  hit ratio.

`apps/data_access/knowledge/embedder.py` is intentionally a thin façade —
no direct `from openai import OpenAI` outside the gateway.

### Stub mode for local dev

Set `KNOWLEDGE_STUB_MODE=True` (or just leave `OPENAI_API_KEY` empty) and
the embedder returns deterministic pseudo-vectors instead of calling
OpenAI. The pipeline runs end-to-end and `search_chunks` works against
your local pgvector, just with low-quality similarity. Useful for testing
extractors / chunker without burning API credit.
