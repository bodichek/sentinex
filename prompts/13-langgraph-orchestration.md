# Prompt 13 — LangGraph Agent Orchestration

## Cíl

Integrovat LangGraph jako orchestrační vrstvu pro Sentinex agenty. Každý agent workflow je reprezentován jako `StateGraph` s podporou checkpointingu přes Redis, tenant izolací a Langfuse tracingem.

## Kontext

- Stack: Django, LangGraph ^0.2, langchain-anthropic, Redis (checkpointer)
- Tenant kontext musí být propagován do každého grafu
- Všechna LLM volání musí mít Langfuse trace
- NE langchain jako celek — pouze `langchain-core` a `langchain-anthropic`

## Acceptance Criteria

### 1. Base infrastructure

- [ ] `apps/agents/graphs/base.py` — `TenantStateGraph` base class
  - Přijímá `tenant_id` v konstruktoru
  - Automaticky injectuje Langfuse callbacks
  - Používá `AsyncRedisCheckpointer` pro state persistence
  - Type-safe `TypedDict` state schema

- [ ] `apps/agents/graphs/state.py` — shared state typy
  ```python
  class AgentState(TypedDict):
      tenant_id: str
      messages: Annotated[list[BaseMessage], add_messages]
      memory_context: list[dict]
      tool_calls: list[dict]
      metadata: dict
  ```

### 2. Checkpointing

- [ ] `apps/agents/checkpointers.py` — Redis checkpointer wrapper
  - Thread ID = `{tenant_id}:{agent_id}:{session_id}`
  - TTL: 24h default, konfigurovatelné per-agent
  - Serializace přes msgpack (ne pickle)

### 3. První konkrétní agent

- [ ] `apps/agents/graphs/research_agent.py` — Research Agent
  - Nodes: `retrieve_context`, `generate_response`, `update_memory`
  - Edge: podmíněný routing na základě confidence score
  - Tool: pgvector similarity search
  - Tool: Graphiti memory read (příprava na prompt 14)

### 4. Django integrace

- [ ] `apps/agents/views.py` — API endpoint pro spuštění agent run
  ```
  POST /api/v1/agents/{agent_type}/run/
  Body: { "input": "...", "session_id": "..." }
  Response: { "run_id": "...", "output": "...", "trace_url": "..." }
  ```
- [ ] Celery task `run_agent_async` pro long-running workflows
- [ ] Django model `AgentRun` pro tracking (tenant-scoped)

### 5. Testy

- [ ] Unit testy pro každý node (mockovat LLM)
- [ ] Integration test pro celý Research Agent workflow
- [ ] Test tenant izolace (různé checkpoints pro různé tenanty)

## Implementační poznámky

```python
# Správně — LangGraph s Anthropic
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langfuse.callback import CallbackHandler

# Checkpointer
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# NIKDY
# from langchain.agents import ...  # Nepoužívat celý LangChain
```

### Tenant izolace v checkpointeru

```python
# Thread ID musí obsahovat tenant_id pro izolaci
config = {
    "configurable": {
        "thread_id": f"{tenant_id}:{agent_id}:{session_id}"
    }
}
await graph.ainvoke(state, config=config)
```

### Langfuse integrace

```python
langfuse_handler = CallbackHandler(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    tags=[f"tenant:{tenant_id}", f"agent:{agent_type}"],
)
config["callbacks"] = [langfuse_handler]
```

## Environment variables (přidat do .env)

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

## Soubory k vytvoření

```
apps/agents/
├── __init__.py
├── models.py           # AgentRun model
├── views.py            # API endpoints
├── urls.py
├── tasks.py            # Celery tasks
├── checkpointers.py    # Redis checkpointer wrapper
├── graphs/
│   ├── __init__.py
│   ├── base.py         # TenantStateGraph
│   ├── state.py        # TypedDict schemas
│   └── research_agent.py
└── tests/
    ├── test_base_graph.py
    ├── test_research_agent.py
    └── test_checkpointer.py
```
