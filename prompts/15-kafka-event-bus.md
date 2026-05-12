# Prompt 15 — Kafka Event Bus

## Cíl

Implementovat Kafka jako event bus pro async komunikaci mezi agenty a systémovými komponentami. Každý tenant má vlastní topic namespace.

## Kontext

- Kafka broker: `localhost:9092` (dev), konfigurovatelné přes env
- Topic naming: `{tenant_id}.events.{category}` 
- Producenti: Django views, Celery tasks, LangGraph nodes
- Konzumenti: ClickHouse sink (analytics), agent subscribers, webhooks

## Acceptance Criteria

### 1. Kafka client wrapper

- [ ] `apps/events/kafka_client.py`
  ```python
  class SentinexKafkaProducer:
      async def publish(
          self,
          tenant_id: str,
          category: str,          # "agent", "system", "user"
          event_type: str,        # "run.started", "run.completed", etc.
          payload: dict,
      ) -> None: ...

  class SentinexKafkaConsumer:
      async def subscribe(
          self,
          tenant_id: str,
          categories: list[str],
          handler: Callable,
      ) -> None: ...
  ```

### 2. Event schema

- [ ] `apps/events/schemas.py` — Pydantic modely pro všechny event typy
  ```python
  class AgentRunEvent(BaseModel):
      event_id: UUID
      tenant_id: str
      agent_type: str
      run_id: UUID
      event_type: Literal["run.started", "run.completed", "run.failed"]
      timestamp: datetime
      payload: dict
      trace_id: str | None  # Langfuse trace ID

  class SystemEvent(BaseModel):
      event_id: UUID
      tenant_id: str
      event_type: str
      timestamp: datetime
      payload: dict
  ```

### 3. Topic management

- [ ] `apps/events/topic_manager.py` — automatické vytváření topics pro nové tenanty
  - Trigger: Django signal při vytvoření tenanta
  - Vytvoří: `{tenant_id}.events.agent`, `{tenant_id}.events.system`, `{tenant_id}.events.user`
  - Retention: 7 dní default

### 4. LangGraph integrace (návaznost na prompt 13)

- [ ] `apps/agents/graphs/nodes/event_nodes.py`
  - `publish_run_started_node` — první node v každém grafu
  - `publish_run_completed_node` — poslední node
  - `publish_run_failed_node` — error handler

### 5. Celery Kafka consumer

- [ ] Celery task `consume_agent_events` — běží jako long-running worker
  - Subscribe na `*.events.agent` pro všechny tenanty
  - Routuje eventy do správných handlerů
  - Dead letter queue pro failed eventy

### 6. Django management command

- [ ] `python manage.py kafka_consumer --tenant=all` — spustí consumer
- [ ] `python manage.py kafka_topics --list` — zobrazí všechny topics
- [ ] `python manage.py kafka_topics --create --tenant={id}` — vytvoří topics pro tenanta

### 7. Testy

- [ ] Unit testy producer/consumer (mock Kafka)
- [ ] Test event schema validace
- [ ] Test topic naming convention

## Event typy (kompletní seznam)

```
agent events:
  run.started
  run.completed
  run.failed
  run.step.completed    # Per LangGraph node

system events:
  tenant.created
  tenant.suspended
  addon.enabled
  addon.disabled

user events:
  user.created
  user.login
  user.action           # Generické user akce
```

## Environment variables

```
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT   # V prod: SASL_SSL
KAFKA_DEFAULT_RETENTION_MS=604800000  # 7 dní
```

## Soubory k vytvoření

```
apps/events/
├── __init__.py
├── kafka_client.py
├── schemas.py
├── topic_manager.py
├── consumers/
│   ├── __init__.py
│   └── agent_consumer.py
├── management/
│   └── commands/
│       ├── kafka_consumer.py
│       └── kafka_topics.py
└── tests/
    ├── test_kafka_client.py
    └── test_schemas.py
```
