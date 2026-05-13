"""Celery tasks that fan-out specialist analysis in parallel."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Any

from celery import shared_task
from django_tenants.utils import schema_context

from apps.agents.base import AgentContext
from apps.agents.specialists import REGISTRY

agent_logger = logging.getLogger("sentinex.agents")


@shared_task(name="agents.run_agent_async")  # type: ignore[untyped-decorator]
def run_agent_async(
    agent_type: str,
    tenant_schema: str,
    tenant_id: str,
    session_id: str,
    payload: dict[str, Any],
    user_id: int | None = None,
) -> dict[str, Any]:
    """Run a LangGraph agent workflow asynchronously and persist an ``AgentRun``."""
    import asyncio
    from datetime import UTC, datetime

    from langchain_core.messages import HumanMessage

    from apps.agents.graphs.research_agent import ResearchAgentGraph
    from apps.agents.models import AgentRun

    graph_classes: dict[str, type] = {"research": ResearchAgentGraph}
    graph_cls = graph_classes.get(agent_type)
    if graph_cls is None:
        raise ValueError(f"Unknown agent_type: {agent_type}")

    with schema_context(tenant_schema):
        run = AgentRun.objects.create(
            agent_type=agent_type,
            session_id=session_id,
            user_id=user_id,
            status=AgentRun.STATUS_RUNNING,
            input=payload,
        )

    try:
        graph = graph_cls(tenant_id=tenant_id)
        state: dict[str, Any] = {
            "tenant_id": tenant_id,
            "agent_id": agent_type,
            "session_id": session_id,
            "messages": [HumanMessage(content=str(payload.get("input", "")))],
            "memory_context": [],
            "metadata": payload.get("metadata") or {},
        }
        result = asyncio.run(graph.ainvoke(state, session_id))
        last = result.get("messages", [])[-1] if result.get("messages") else None
        output_text = getattr(last, "content", "") if last else ""

        with schema_context(tenant_schema):
            run.status = AgentRun.STATUS_SUCCEEDED
            run.output = {"text": output_text}
            run.finished_at = datetime.now(UTC)  # type: ignore[assignment]
            run.save(update_fields=["status", "output", "finished_at"])
        return {"run_id": str(run.id), "output": output_text}
    except Exception as exc:
        agent_logger.exception("agent run failed")
        with schema_context(tenant_schema):
            run.status = AgentRun.STATUS_FAILED
            run.error = str(exc)
            run.finished_at = datetime.now(UTC)  # type: ignore[assignment]
            run.save(update_fields=["status", "error", "finished_at"])
        raise


@shared_task(name="agents.run_specialist")  # type: ignore[untyped-decorator]
def run_specialist(specialist_name: str, context_dict: dict[str, Any]) -> dict[str, Any]:
    """Run a single specialist. Meant to be composed in a Celery ``group``."""
    tenant_schema = context_dict.get("tenant_schema") or "public"
    context = AgentContext(**context_dict)
    specialist_cls = REGISTRY[specialist_name]

    start = time.monotonic()
    status = "ok"
    try:
        with schema_context(tenant_schema):
            response = specialist_cls().analyze(context)
    except Exception:
        status = "error"
        latency_ms = int((time.monotonic() - start) * 1000)
        agent_logger.info(
            json.dumps(
                {
                    "event": "agent_run",
                    "tenant": tenant_schema,
                    "specialist": specialist_name,
                    "latency_ms": latency_ms,
                    "status": status,
                }
            )
        )
        raise

    latency_ms = int((time.monotonic() - start) * 1000)
    agent_logger.info(
        json.dumps(
            {
                "event": "agent_run",
                "tenant": tenant_schema,
                "specialist": specialist_name,
                "latency_ms": latency_ms,
                "status": status,
            }
        )
    )

    return {
        "name": response.name,
        "content": response.content,
        "structured_data": response.structured_data,
        "confidence": response.confidence,
        "usage": asdict(response.usage) if response.usage is not None else None,
    }
