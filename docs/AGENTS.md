# Agent Layer

This document describes the design of the Agent Layer in Sentinex.

## Overview

The Agent Layer is the intelligent core of the platform. It handles all AI interactions: user queries, scheduled analyses, addon-triggered actions.

Architecture principles:
- Orchestrator-Specialist pattern
- Memory as first-class concept (short, medium, long-term)
- Guardrails are mandatory, not optional
- Multi-model routing from day 1
- All LLM calls are asynchronous (Celery-based)

## Components

### Orchestrator

Central coordinator. Every user-initiated query passes through the Orchestrator.

Responsibilities:
1. Receive query with full context (user, tenant, permissions, memory)
2. Classify intent (strategic, finance, people, customer, other)
3. Determine which specialists are needed
4. Invoke specialists in parallel
5. Aggregate specialist responses
6. Compose final, human-ready output
7. Pass through post-call guardrails

Implementation:
- Lives in `apps/agents/orchestrator.py`
- Uses Claude Sonnet (default)
- Stateless — state lives in memory system
- Parallelization via Celery group tasks

### Specialists

Domain-specific agents with focused expertise.

**Strategic Specialist**
- Domain: high-level business analysis, quarterly planning, risk assessment
- Tools: Insight Functions for strategic metrics, historical decision log
- Model: Claude Sonnet

**Finance Specialist**
- Domain: financial signals, cash flow, unit economics
- Tools: Finance-related Insight Functions, direct access to synced financial data
- Model: Claude Sonnet (complex), Claude Haiku (simple queries)

**People Specialist**
- Domain: team health, organizational signals, accountability
- Tools: People-related Insight Functions, team activity metrics
- Model: Claude Sonnet
- EU AI Act consideration: never performs sentiment analysis of employees without explicit consent

**Customer Specialist**
- Domain: pipeline, deal risk, customer health
- Tools: Customer-related Insight Functions, CRM-synced data
- Model: Claude Sonnet

**Addon Specialists**
- Addons can register their own specialists
- Addon specialists follow the same interface as core specialists
- Registered via addon manifest

### Memory System

Three tiers of memory, each with different retention and retrieval semantics.

**Short-term memory**
- Scope: current conversation
- Storage: Redis, TTL 2 hours
- Content: recent messages, agent state
- Retrieval: full context

**Medium-term memory**
- Scope: last 30 days per user/tenant
- Storage: Postgres, structured facts
- Content: key decisions, actions, changes in state
- Retrieval: semantic search via pgvector

**Long-term memory**
- Scope: unlimited, per tenant
- Storage: Postgres with pgvector embeddings
- Content: company knowledge base, OPSPs, board minutes, strategic artifacts
- Retrieval: RAG with reranking

Memory is never cross-tenant. Every query includes tenant filter.

### Guardrails

Mandatory pre-call and post-call checks.

**Pre-call guardrails**
1. Cost budget check: verify conversation budget not exceeded
2. Scope validation: verify agent is authorized for requested action
3. PII masking: replace PII with tokens before sending to LLM
4. Prompt injection detection: basic pattern matching

**Post-call guardrails**
1. Output validation: structure check, format check
2. PII unmasking: replace tokens with originals for authorized users
3. Compliance logging: log the call for audit (EU AI Act requirement)
4. Hallucination detection: for factual claims, verify against data source

Implementation lives in `apps/agents/guardrails.py`. Every agent invocation wraps through guardrails. Bypassing requires explicit comment explaining why.

### Context Builder

Assembles the prompt context for each LLM call.

Process:
1. Fetch relevant Insight Function outputs
2. Fetch memory (short + medium + long-term as appropriate)
3. Apply PII masking
4. Construct prompt per specialist's template
5. Apply token budget (truncate oldest memory if needed)
6. Compute prompt hash for caching

Implementation: `apps/agents/context_builder.py`.

### LLM Gateway

Thin wrapper over LLM provider SDKs.

Responsibilities:
- Model routing (Sonnet vs Haiku based on task complexity)
- Token counting per tenant
- Caching (Redis exact-match on prompt hash)
- Retry logic (exponential backoff on rate limits)
- Error handling and fallback
- Telemetry (latency, cost, success rate)

Implementation: `apps/agents/llm_gateway.py`.

Rules:
- No LLM call should bypass the gateway
- All direct Anthropic SDK usage is forbidden outside the gateway
- Gateway is the only place where `ANTHROPIC_API_KEY` is used

## Agent Execution Flow

```
User query
    ↓
Orchestrator.handle(query, context)
    ↓
Guardrails.pre_call(query)
    ↓
ContextBuilder.build(intent, memory, insight_funcs)
    ↓
Parallel specialist invocations (Celery group)
    ├── StrategicAgent.analyze(context)
    ├── FinanceAgent.analyze(context)
    └── PeopleAgent.analyze(context)
    ↓
Each specialist:
    - Calls LLMGateway.complete(prompt, model="sonnet")
    - Returns structured response
    ↓
Orchestrator.compose(specialist_responses)
    ↓
Guardrails.post_call(final_response)
    ↓
Return to caller (view, task, addon)
```

## Prompt Management

System prompts are stored in YAML files for versioning and review:

```
apps/agents/prompts/
├── orchestrator.yaml
├── strategic_specialist.yaml
├── finance_specialist.yaml
├── people_specialist.yaml
└── customer_specialist.yaml
```

Example:
```yaml
# apps/agents/prompts/strategic_specialist.yaml

name: strategic_specialist
version: "0.1.0"
model: claude-sonnet-4-20250514
max_tokens: 4096
temperature: 0.3

system: |
  You are a strategic business analyst for Sentinex.

  Your role is to analyze high-level business signals and provide
  insights on strategic direction, quarterly priorities, and risks.

  You have access to:
  - Insight Functions for strategic metrics
  - Company decision history
  - Current quarterly priorities and targets

  Rules:
  - Cite specific data points when making claims
  - Never fabricate numbers or facts
  - Acknowledge uncertainty explicitly
  - Output in Czech when the conversation is in Czech
  - Output in English when the conversation is in English
```

Prompts are versioned in git. Changes require code review.

## Cost Management

Every LLM call has a cost. Tracked per tenant.

Budget enforcement:
- Per-conversation budget (default: 50 CZK)
- Per-tenant monthly budget (set per subscription plan)
- Alerts at 80% and 100% of budget

When budget exceeded:
- New queries receive "budget exceeded" response
- Admin can temporarily raise budget
- Scheduled tasks skip execution (logged for review)

## Adding a New Specialist

### 1. Create specialist file

```python
# apps/agents/specialists/risk_specialist.py

from apps.agents.base import BaseSpecialist

class RiskSpecialist(BaseSpecialist):
    name = "risk"
    system_prompt_file = "risk_specialist.yaml"

    def get_insight_functions(self):
        return [
            "get_strategic_risks",
            "get_recent_anomalies",
        ]

    def analyze(self, context):
        # Specialist-specific logic
        return self.llm_complete(context)
```

### 2. Create prompt YAML

Add `apps/agents/prompts/risk_specialist.yaml`.

### 3. Register in Orchestrator

```python
# apps/agents/orchestrator.py

SPECIALISTS = {
    "strategic": StrategicSpecialist,
    "finance": FinanceSpecialist,
    "people": PeopleSpecialist,
    "customer": CustomerSpecialist,
    "risk": RiskSpecialist,  # New
}
```

### 4. Update intent classifier

Classifier must be aware of new intent types.

### 5. Write tests

- Unit test for specialist logic
- Integration test for end-to-end flow

## Testing Agents

### Unit tests

Mock the LLM gateway, test business logic:

```python
def test_finance_specialist_analyzes_cash_flow(mocker):
    mock_llm = mocker.patch("apps.agents.llm_gateway.complete")
    mock_llm.return_value = "Cash flow is healthy."

    specialist = FinanceSpecialist()
    result = specialist.analyze(context={"org": org})

    assert "healthy" in result
    mock_llm.assert_called_once()
```

### Integration tests

Use real LLM calls in CI (with limited scope):

```python
@pytest.mark.integration
def test_orchestrator_end_to_end():
    # Real LLM call, limited tokens
    orchestrator = Orchestrator()
    response = orchestrator.handle(
        query="What are our main risks?",
        context={"org": org, "user": user},
    )
    assert response is not None
```

## Debugging Agents

### Logging

Every LLM call logged with:
- Timestamp
- Tenant
- User
- Specialist invoked
- Prompt hash (not full prompt, for privacy)
- Token usage
- Cost
- Latency
- Outcome (success/error)

### Replay

Conversations can be replayed for debugging:

```bash
poetry run python manage.py replay_conversation <conversation_id>
```

This re-runs the conversation without actually calling LLMs, using stored responses.

## Future Additions (Post-MVP)

- Multi-turn conversations (chat-style)
- Agent hand-off (one specialist delegating to another)
- Tool use (agent calling functions beyond Insight Functions)
- Self-reflection (agent critiquing its own output)
- On-premise LLM support (Qwen, Llama via vLLM)
- Semantic caching (beyond exact-match)
