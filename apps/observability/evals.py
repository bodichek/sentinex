"""Lightweight eval framework that posts scores back to Langfuse."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.observability.langfuse_client import get_client

logger = logging.getLogger("sentinex.observability.evals")


def eval_hallucination_score(answer: str, context: str) -> float:
    """Cheap lexical hallucination heuristic — 1.0 = grounded, 0.0 = ungrounded.

    Counts the share of answer tokens (>= 4 chars) that also appear in the
    supporting context. Sufficient as a placeholder until an LLM-as-judge
    eval is wired up.
    """
    if not answer.strip():
        return 1.0
    tokens = [t.lower() for t in answer.split() if len(t) >= 4]
    if not tokens:
        return 1.0
    ctx = context.lower()
    grounded = sum(1 for t in tokens if t in ctx)
    return round(grounded / len(tokens), 4)


def eval_relevance_score(answer: str, query: str) -> float:
    """Token-overlap relevance score in [0, 1]."""
    qa = {t.lower() for t in query.split() if len(t) >= 3}
    aa = {t.lower() for t in answer.split() if len(t) >= 3}
    if not qa:
        return 0.0
    return round(len(qa & aa) / len(qa), 4)


@shared_task(name="observability.post_eval")  # type: ignore[untyped-decorator]
def post_eval(
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
) -> None:
    """Post an eval score back to Langfuse asynchronously."""
    client = get_client()
    sdk = client._get_sdk()  # noqa: SLF001
    if sdk is None:
        logger.debug("langfuse disabled; skipping eval %s=%s", name, value)
        return
    try:
        sdk.score(trace_id=trace_id, name=name, value=value, comment=comment)
    except Exception:  # noqa: BLE001
        logger.exception("failed to post eval %s for trace %s", name, trace_id)


def evaluate_and_post(
    trace_id: str,
    *,
    answer: str,
    query: str,
    context: str,
    async_: bool = True,
) -> dict[str, float]:
    """Compute the bundled scores and (optionally) push them via Celery."""
    scores = {
        "hallucination": eval_hallucination_score(answer, context),
        "relevance": eval_relevance_score(answer, query),
    }
    for name, value in scores.items():
        if async_:
            post_eval.delay(trace_id, name, value)
        else:
            post_eval.run(trace_id, name, value)
    return scores
