"""Trello sync — board / card / activity aggregates."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.trello.client import TrelloClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    closed = sum(1 for c in cards if c.get("closed"))
    overdue = 0
    completed = 0
    now = timezone.now()
    for c in cards:
        due = c.get("due")
        if due and not c.get("dueComplete"):
            try:
                due_dt = timezone.datetime.fromisoformat(due.replace("Z", "+00:00"))
                if due_dt < now:
                    overdue += 1
            except Exception:
                pass
        if c.get("dueComplete"):
            completed += 1
    return {
        "total": len(cards),
        "open": len(cards) - closed,
        "closed": closed,
        "overdue": overdue,
        "completed": completed,
    }


def _summarise_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: Counter[str] = Counter(str(a.get("type") or "unknown") for a in actions)
    actors = {(a.get("idMemberCreator") or "") for a in actions}
    return {
        "total": len(actions),
        "active_members": len([a for a in actors if a]),
        "by_type": dict(by_type),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="trello", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)
    since_iso = (timezone.now() - timedelta(days=days)).isoformat()

    with TrelloClient(integration) as client:
        try:
            boards = [b for b in client.list_boards() if not b.get("closed")]
        except Exception as exc:
            logger.exception("Trello board listing failed: %s", exc)
            return None

        per_board: list[dict[str, Any]] = []
        all_cards: list[dict[str, Any]] = []
        all_actions: list[dict[str, Any]] = []
        for b in boards[:25]:  # cap fan-out
            board_id = b.get("id")
            if not board_id:
                continue
            try:
                cards = client.list_cards(board_id, since_iso=since_iso)
                actions = client.list_actions(board_id, since_iso=since_iso, limit=500)
            except Exception as exc:
                logger.warning("Trello board %s skipped: %s", board_id, exc)
                continue
            per_board.append(
                {
                    "id": board_id,
                    "name": b.get("name"),
                    "url": b.get("url"),
                    "cards": _summarise_cards(cards),
                    "actions": _summarise_actions(actions),
                }
            )
            all_cards.extend(cards)
            all_actions.extend(actions)

    snapshot = DataSnapshot.objects.create(
        source="trello",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "boards": {"data": {"count": len(boards), "items": per_board}, "ok": True},
            "cards": {"data": _summarise_cards(all_cards), "ok": True},
            "actions": {"data": _summarise_actions(all_actions), "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot
