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
