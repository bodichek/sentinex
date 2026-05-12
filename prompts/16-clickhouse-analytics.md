# Prompt 16 — ClickHouse Analytics Store

## Cíl

Implementovat ClickHouse jako analytics store pro agent run metriky, usage data, audit trail a business intelligence. Data přichází z Kafka (consumer) i přímým zápisem z Django.

## Kontext

- ClickHouse je OLAP databáze optimalizovaná pro analytické dotazy
- Data flow: Kafka → ClickHouse consumer → ClickHouse tabulky
- Django čte agregovaná data pro dashboardy a billing
- Tenant izolace přes `tenant_id` sloupec (ne separátní databáze)

## Acceptance Criteria

### 1. ClickHouse schema

- [ ] `infra/clickhouse/init.sql` — inicializační SQL
  
  ```sql
  -- Agent runs tabulka (hlavní)
  CREATE TABLE IF NOT EXISTS agent_runs (
      tenant_id       String,
      run_id          UUID,
      agent_type      String,
      session_id      String,
      status          Enum8('started'=1, 'completed'=2, 'failed'=3),
      started_at      DateTime64(3),
      completed_at    DateTime64(3) DEFAULT 0,
      duration_ms     UInt32 DEFAULT 0,
      input_tokens    UInt32 DEFAULT 0,
      output_tokens   UInt32 DEFAULT 0,
      total_cost_usd  Float32 DEFAULT 0,
      trace_id        String DEFAULT '',
      metadata        String DEFAULT '{}'  -- JSON
  ) ENGINE = MergeTree()
  PARTITION BY toYYYYMM(started_at)
  ORDER BY (tenant_id, started_at, run_id);

  -- LLM calls tabulka (per call detail)
  CREATE TABLE IF NOT EXISTS llm_calls (
      tenant_id       String,
      run_id          UUID,
      call_id         UUID,
      model           String,
      input_tokens    UInt32,
      output_tokens   UInt32,
      latency_ms      UInt32,
      cost_usd        Float32,
      called_at       DateTime64(3),
      trace_id        String DEFAULT ''
  ) ENGINE = MergeTree()
  PARTITION BY toYYYYMM(called_at)
  ORDER BY (tenant_id, called_at, call_id);

  -- System events (audit trail)
  CREATE TABLE IF NOT EXISTS system_events (
      tenant_id       String,
      event_id        UUID,
      event_type      String,
      payload         String,  -- JSON
      created_at      DateTime64(3)
  ) ENGINE = MergeTree()
  PARTITION BY toYYYYMM(created_at)
  ORDER BY (tenant_id, created_at, event_id);
  ```

### 2. ClickHouse client

- [ ] `apps/analytics/clickhouse_client.py`
  ```python
  class SentinexClickHouseClient:
      async def insert_agent_run(self, run: AgentRunRow) -> None: ...
      async def insert_llm_call(self, call: LlmCallRow) -> None: ...
      async def get_tenant_usage(
          self,
          tenant_id: str,
          from_date: date,
          to_date: date,
      ) -> TenantUsageSummary: ...
      async def get_agent_metrics(
          self,
          tenant_id: str,
          agent_type: str | None = None,
          period: str = "7d",
      ) -> list[AgentMetricRow]: ...
  ```

### 3. Kafka → ClickHouse consumer

- [ ] `apps/analytics/consumers/clickhouse_sink.py`
  - Subscribe na `*.events.agent` a `*.events.system` pro všechny tenanty
  - Batch insert do ClickHouse (každých 100 eventů nebo 5 sekund)
  - Idempotentní (deduplikace přes `event_id`)

### 4. Django API — analytics endpoints

- [ ] `GET /api/v1/analytics/usage/` — usage summary pro aktuální tenant
  ```json
  {
    "period": "2025-01",
    "agent_runs": 1247,
    "total_tokens": 8432100,
    "total_cost_usd": 42.16,
    "by_agent_type": {...}
  }
  ```
- [ ] `GET /api/v1/analytics/runs/` — seznam posledních run s metrikami
- [ ] `GET /api/v1/analytics/costs/` — cost breakdown (pro billing)

### 5. Billing integrace (návaznost na prompt 09)

- [ ] `apps/billing/usage_tracker.py` — čte z ClickHouse pro billing period
  - Používá ClickHouse agregace místo PostgreSQL pro výkon
  - Cache výsledků v Redis (TTL: 1h)

### 6. Testy

- [ ] Unit testy pro ClickHouse client (mock klient)
- [ ] Test Kafka consumer → ClickHouse insert flow
- [ ] Test analytics API endpoints

## Datové typy (Pydantic)

```python
class AgentRunRow(BaseModel):
    tenant_id: str
    run_id: UUID
    agent_type: str
    session_id: str
    status: Literal["started", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    trace_id: str = ""
    metadata: dict = {}
```

## Environment variables

```
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DATABASE=sentinex
CLICKHOUSE_USER=sentinex
CLICKHOUSE_PASSWORD=sentinex_ch
```

## Soubory k vytvoření

```
apps/analytics/
├── __init__.py
├── clickhouse_client.py
├── views.py
├── urls.py
├── schemas.py        # Pydantic row types
├── consumers/
│   └── clickhouse_sink.py
└── tests/
    ├── test_clickhouse_client.py
    └── test_analytics_api.py

infra/clickhouse/
└── init.sql
```
