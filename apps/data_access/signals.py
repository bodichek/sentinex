"""Signal handlers: index DataSnapshot summaries into long-term memory."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.data_access.models import DataSnapshot

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DataSnapshot)
def _index_snapshot_summary(sender: type, instance: DataSnapshot, created: bool, **kwargs: Any) -> None:
    if not created:
        return
    try:
        from apps.agents.memory import LongTermMemory
    except Exception:
        return
    summary = _summarize(instance)
    if not summary:
        return
    LongTermMemory().index(
        summary,
        source="insight",
        metadata={
            "snapshot_source": instance.source,
            "period_end": instance.period_end.isoformat(),
        },
    )


def _summarize(snapshot: DataSnapshot) -> str:
    metrics = snapshot.metrics or {}
    try:
        return f"{snapshot.source} snapshot {snapshot.period_end}: {json.dumps(metrics, default=str)[:1000]}"
    except Exception:
        return ""
