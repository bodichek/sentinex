"""Weekly Brief generator service."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.utils import timezone

from apps.addons.weekly_brief.models import WeeklyBriefReport
from apps.agents.llm_gateway import complete
from apps.agents.memory import LongTermMemory
from apps.data_access.insight_functions import (
    get_cashflow_snapshot,
    get_recent_anomalies,
    get_team_activity_summary,
    get_upcoming_commitments,
    get_weekly_metrics,
)
from apps.data_access.insight_functions.exceptions import InsufficientData

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    data = yaml.safe_load((PROMPTS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return str(data["system"]).strip()


class WeeklyBriefGenerator:
    """Compose a weekly brief from Insight Functions + LLM executive summary."""

    def __init__(self, *, llm: Any = complete) -> None:
        self._llm = llm

    def generate(self, *, period_end: date | None = None) -> WeeklyBriefReport:
        period_end = period_end or timezone.now().date()
        period_start = period_end - timedelta(days=7)

        existing = WeeklyBriefReport.objects.filter(
            period_start=period_start, period_end=period_end
        ).first()
        if existing is not None and existing.status == WeeklyBriefReport.STATUS_GENERATED:
            return existing

        sections = self._collect_sections()
        summary = self._compose_summary(sections)

        html_body = render_to_string(
            "addons/weekly_brief/email/brief.html",
            {"summary": summary, "sections": sections, "period_start": period_start, "period_end": period_end},
        )
        plain_body = render_to_string(
            "addons/weekly_brief/email/brief.txt",
            {"summary": summary, "sections": sections, "period_start": period_start, "period_end": period_end},
        )

        # JSONField must store serialisable primitives — round-trip through encoder.
        serialisable = json.loads(json.dumps(sections, cls=DjangoJSONEncoder))
        report, _ = WeeklyBriefReport.objects.update_or_create(
            period_start=period_start,
            period_end=period_end,
            defaults={
                "content": {"summary": summary, "sections": serialisable},
                "html_body": html_body,
                "plain_body": plain_body,
                "status": WeeklyBriefReport.STATUS_GENERATED,
                "generated_at": timezone.now(),
            },
        )
        # Auto-index the brief into long-term memory; failures are non-fatal.
        LongTermMemory().index(
            summary,
            source="brief",
            metadata={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "report_uuid": str(report.uuid),
            },
        )
        return report

    # ------------------------------------------------------------------

    def _collect_sections(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        out["weekly_metrics"] = _safe(get_weekly_metrics)
        out["cashflow"] = _safe(get_cashflow_snapshot)
        out["anomalies"] = _safe(get_recent_anomalies)
        out["team_activity"] = _safe(get_team_activity_summary)
        out["commitments"] = _safe(get_upcoming_commitments)
        return out

    def _compose_summary(self, sections: dict[str, Any]) -> str:
        system = _load_prompt("brief_composer")
        prompt = f"Data:\n{sections}"
        try:
            response = self._llm(prompt, model="sonnet", system=system, temperature=0.4, max_tokens=1024)
        except Exception as exc:
            logger.exception("Weekly brief summary generation failed")
            return f"(Executive summary unavailable — LLM error: {exc})"
        return str(response.content)


def _safe(func: Any) -> Any:
    try:
        result = func()
    except InsufficientData as exc:
        return {"error": "insufficient_data", "detail": str(exc)}
    except Exception as exc:
        logger.exception("insight function failed: %s", getattr(func, "__name__", ""))
        return {"error": "failure", "detail": str(exc)}
    if hasattr(result, "__dataclass_fields__"):
        return asdict(result)
    if isinstance(result, list):
        return [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in result]
    return result
