# Prompt 14 — Graphiti + Neo4j Knowledge Graph

## Cíl

Integrovat Graphiti jako temporal knowledge graph pro paměť agentů a Neo4j jako graph databázi pro entity relationships. Každý tenant má vlastní Neo4j databázi.

## Kontext

- Graphiti poskytuje temporal vrstvu — entity mají časové platnosti (valid_from, valid_to)
- Neo4j ukládá: Entity, Relations, Episodes
- Graphiti používá Neo4j jako backend + LLM pro extrakci entit
- Tenant izolace: každý tenant = vlastní Neo4j database (nebo prefix v komunitní verzi)

## Acceptance Criteria

### 1. Neo4j setup

- [ ] `apps/memory/neo4j_client.py` — tenant-aware Neo4j client
  ```python
  class TenantNeo4jClient:
      def get_driver(self, tenant_id: str) -> AsyncDriver: ...
      def get_database_name(self, tenant_id: str) -> str: ...
      # Vrací: "tenant_{tenant_id}" nebo "neo4j" s tenant filtrem
  ```
- [ ] `infra/neo4j/init.cypher` — inicializační Cypher skripty
  - Indexy pro rychlé vyhledávání
  - Constraints pro unikátnost entit

### 2. Graphiti integrace

- [ ] `apps/memory/graphiti_client.py` — Graphiti wrapper
  ```python
  class TenantGraphitiClient:
      async def add_episode(
          self,
          tenant_id: str,
          content: str,
          source: EpisodeType,
          metadata: dict,
      ) -> Episode: ...

      async def search(
          self,
          tenant_id: str,
          query: str,
          num_results: int = 10,
      ) -> list[EntityEdge]: ...
  ```
- [ ] LLM pro Graphiti = Anthropic Claude (claude-haiku-4-5 pro rychlost a cenu)
- [ ] Embeddings = `text-embedding-3-small` přes OpenAI NEBO pgvector s Anthropic embeddings

### 3. Django modely

- [ ] `apps/memory/models.py`
  - `KnowledgeEpisode` — tracking co bylo přidáno do grafu (tenant-scoped)
  - `MemorySnapshot` — periodické snapshoty stavu grafu pro audit

### 4. LangGraph integrace (návaznost na prompt 13)

- [ ] `apps/agents/graphs/nodes/memory_nodes.py`
  - `read_memory_node` — před LLM voláním načte relevantní kontext z Graphiti
  - `write_memory_node` — po LLM odpovědi uloží nové poznatky do Graphiti
  
  ```python
  async def read_memory_node(state: AgentState) -> AgentState:
      results = await graphiti_client.search(
          tenant_id=state["tenant_id"],
          query=state["messages"][-1].content,
      )
      state["memory_context"] = [r.dict() for r in results]
      return state
  ```

### 5. API endpoints

- [ ] `GET /api/v1/memory/entities/` — seznam entit pro tenanta
- [ ] `GET /api/v1/memory/search/?q=...` — semantic search v grafu
- [ ] `POST /api/v1/memory/episode/` — manuální přidání episody
- [ ] `DELETE /api/v1/memory/entity/{id}/` — smazání entity

### 6. Testy

- [ ] Unit testy pro `TenantNeo4jClient` (mock driver)
- [ ] Unit testy pro `TenantGraphitiClient` (mock LLM + Neo4j)
- [ ] Integration test: přidání episody → search vrátí relevantní výsledek
- [ ] Test tenant izolace: tenant A nevidí data tenant B

## Environment variables

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=sentinex_neo4j
NEO4J_TENANT_ISOLATION=database  # nebo "prefix"

# Pro Graphiti embeddings (pokud OpenAI)
OPENAI_API_KEY=sk-...
```

## Poznámky k tenant izolaci

**Komunity Neo4j** (bez Enterprise):
```python
# Použij prefix v node properties
MATCH (e:Entity {tenant_id: $tenant_id}) RETURN e
```

**Enterprise Neo4j** (produkce):
```python
# Každý tenant = vlastní databáze
database = f"tenant{tenant_id.replace('-', '')}"
session = driver.session(database=database)
```

Pro dev použij prefix variantu, pro prod switch na databáze.

## Soubory k vytvoření

```
apps/memory/
├── __init__.py
├── models.py
├── views.py
├── urls.py
├── neo4j_client.py
├── graphiti_client.py
└── tests/
    ├── test_neo4j_client.py
    └── test_graphiti_client.py

infra/
└── neo4j/
    └── init.cypher
```
