# Prompt 17 — Langfuse LLM Observability

## Cíl

Implementovat Langfuse jako LLM observability vrstvu — tracing všech LLM volání, eval framework a prompt management. Každý tenant má vlastní Langfuse project nebo je tagged.

## Kontext

- Langfuse běží lokálně na `localhost:3000` (viz docker-compose)
- Integrace přes LangChain callback handler (automaticky funguje s LangGraph)
- Přímá SDK integrace pro non-LangGraph volání
- Tenant izolace přes tags nebo separátní projects

## Acceptance Criteria

### 1. Langfuse klient wrapper

- [ ] `apps/observability/langfuse_client.py`
  ```python
  class SentinexLangfuseClient:
      def get_callback_handler(
          self,
          tenant_id: str,
          agent_type: str,
          run_id: str,
      ) -> CallbackHandler: ...

      def trace(
          self,
          tenant_id: str,
          name: str,
          input: dict,
          output: dict | None = None,
          metadata: dict | None = None,
      ) -> StatefulTraceClient: ...
  ```

### 2. LangGraph automatická integrace

- [ ] Aktualizovat `apps/agents/graphs/base.py` (z promptu 13)
  - `TenantStateGraph` automaticky přidává Langfuse callback do každého invoke
  - Trace URL se vrací v API response
  - Generace (LLM calls) jsou automaticky trackované

### 3. Přímá SDK integrace (mimo LangGraph)

- [ ] Django middleware `LangfuseRequestMiddleware`
  - Vytvoří trace pro každý API request (volitelné, opt-in per endpoint)
  - Propaguje trace ID do request context

- [ ] Decorator pro manual tracing
  ```python
  @langfuse_trace(name="custom_llm_call", tenant_from="request")
  async def my_anthropic_call(request, prompt: str) -> str:
      ...
  ```

### 4. Prompt management

- [ ] `apps/observability/prompt_manager.py`
  - Stahuje prompty z Langfuse prompt registry
  - Cache v Redis (TTL: 5 minut)
  - Fallback na local prompts pokud Langfuse nedostupný
  ```python
  async def get_prompt(name: str, version: int | None = None) -> str: ...
  async def push_prompt(name: str, content: str, labels: list[str]) -> None: ...
  ```

### 5. Evals framework

- [ ] `apps/observability/evals.py` — základní eval funkce
  - `eval_hallucination_score` — detekce halucinací
  - `eval_relevance_score` — relevance odpovědi k query
  - Evals se posílají zpět do Langfuse asynchronně (Celery task)

### 6. Dashboard data

- [ ] `GET /api/v1/observability/traces/` — seznam traces pro tenant
  - Filtrování: `agent_type`, `date_from`, `date_to`, `status`
  - Vrací Langfuse trace URL pro každý run

### 7. Alerting

- [ ] Celery periodic task `check_error_rate`
  - Každých 5 minut zkontroluje error rate z Langfuse
  - Pokud > 10% za posledních 30 minut → Django signal → notifikace

### 8. Testy

- [ ] Unit testy pro klient wrapper (mock Langfuse SDK)
- [ ] Test callback handler integrace s LangGraph
- [ ] Test prompt manager s cache

## Tenant izolace strategie

**Option A — Tags** (jednodušší, doporučeno pro start):
```python
CallbackHandler(
    tags=[f"tenant:{tenant_id}", f"env:{settings.ENV}"]
)
```

**Option B — Separátní projects** (lepší izolace, vyžaduje více API klíčů):
```python
# Každý tenant má vlastní Langfuse project key
# Uloženo v Tenant modelu: langfuse_public_key, langfuse_secret_key
```

Implementuj Option A, připrav migraci na Option B pro Enterprise tenanty.

## Environment variables

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_ENABLED=true
LANGFUSE_SAMPLE_RATE=1.0  # 1.0 = všechna volání, 0.1 = 10%
```

## Soubory k vytvoření / upravit

```
apps/observability/
├── __init__.py
├── langfuse_client.py
├── prompt_manager.py
├── evals.py
├── middleware.py
├── decorators.py
├── views.py
├── urls.py
└── tests/
    ├── test_langfuse_client.py
    └── test_prompt_manager.py

# Upravit (z prompt 13):
apps/agents/graphs/base.py   # Přidat Langfuse callback
```
