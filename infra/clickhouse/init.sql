-- Sentinex — ClickHouse analytics schema.

CREATE DATABASE IF NOT EXISTS sentinex;

CREATE TABLE IF NOT EXISTS sentinex.agent_runs (
    tenant_id       String,
    run_id          UUID,
    agent_type      String,
    session_id      String,
    status          Enum8('started' = 1, 'completed' = 2, 'failed' = 3),
    started_at      DateTime64(3),
    completed_at    DateTime64(3) DEFAULT toDateTime64(0, 3),
    duration_ms     UInt32 DEFAULT 0,
    input_tokens    UInt32 DEFAULT 0,
    output_tokens   UInt32 DEFAULT 0,
    total_cost_usd  Float32 DEFAULT 0,
    trace_id        String DEFAULT '',
    metadata        String DEFAULT '{}'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (tenant_id, started_at, run_id);

CREATE TABLE IF NOT EXISTS sentinex.llm_calls (
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

CREATE TABLE IF NOT EXISTS sentinex.system_events (
    tenant_id       String,
    event_id        UUID,
    event_type      String,
    payload         String,
    created_at      DateTime64(3)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id, created_at, event_id);
