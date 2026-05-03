"""Tool registry — bridges Insight Functions to the Anthropic tool-use API.

Every entry exposes:
- ``name``: identifier seen by the model (matches the insight function name).
- ``description``: short, action-oriented explanation in English; the model
  reads this to decide whether to call the tool.
- ``input_schema``: JSON Schema of arguments (kwargs) the function takes.
- ``invoke``: Python callable that executes the tool and returns a dict.

The dispatcher serialises every tool result as a JSON string so the model
sees structured numbers without parsing prose.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from apps.data_access.insight_functions import (
    get_cashflow_snapshot,
    get_marketing_funnel,
    get_pipeline_velocity,
    get_project_throughput,
    get_recent_anomalies,
    get_slack_activity,
    get_team_activity_summary,
    get_upcoming_commitments,
    get_weekly_metrics,
    search_company_knowledge,
)
from apps.data_access.insight_functions.exceptions import InsufficientData


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def _wrap(fn: Callable[..., Any]) -> Callable[..., dict[str, Any]]:
    def runner(**kwargs: Any) -> dict[str, Any]:
        try:
            return {"ok": True, "data": _serialize(fn(**kwargs))}
        except InsufficientData as exc:
            return {"ok": False, "error": "insufficient_data", "reason": str(exc)}
        except Exception as exc:  # pragma: no cover — defensive
            return {"ok": False, "error": exc.__class__.__name__, "reason": str(exc)}

    return runner


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


TOOLS: dict[str, dict[str, Any]] = {
    "get_weekly_metrics": {
        "description": (
            "Strategic overview — counts of e-mails, calendar events and Drive "
            "changes over the most recent ISO week. Use to give the user a "
            "high-level pulse of the company in the last 7 days."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "invoke": _wrap(get_weekly_metrics),
    },
    "get_recent_anomalies": {
        "description": (
            "List anomalies (sudden drops or spikes in core signals) detected "
            "across the last N days. Returns one entry per anomaly with kind, "
            "severity and supporting numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_recent_anomalies),
    },
    "get_team_activity_summary": {
        "description": (
            "Team activity in the last N days — calendar events, e-mail "
            "threads, unique correspondents. Use for people-management "
            "questions and load monitoring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 60, "default": 7},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_team_activity_summary),
    },
    "get_upcoming_commitments": {
        "description": (
            "Upcoming commitments (calendar events with attendees, deadlines "
            "embedded in calendar) over the next N days."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "minimum": 1, "maximum": 60, "default": 7},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_upcoming_commitments),
    },
    "get_cashflow_snapshot": {
        "description": (
            "Latest cashflow snapshot — cash on hand, monthly revenue / "
            "expenses, runway months. Use for finance questions."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "invoke": _wrap(get_cashflow_snapshot),
    },
    "get_slack_activity": {
        "description": (
            "Slack workspace activity in the last N days — channels, total "
            "messages, active users, top channels by volume."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_slack_activity),
    },
    "get_marketing_funnel": {
        "description": (
            "Latest e-mail marketing performance — total contacts, list "
            "count, open rate, CTR, top campaigns. Source-agnostic across "
            "SmartEmailing / Ecomail / Mailchimp; the result includes a "
            "'source' field so you can quote which ESP's data is shown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 30},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_marketing_funnel),
    },
    "get_pipeline_velocity": {
        "description": (
            "Latest sales pipeline velocity — open / won / lost deal counts, "
            "win rate, total open value, won value, average open deal, "
            "activity completion rate, distribution by stage. Source-agnostic "
            "across Pipedrive / HubSpot / Salesforce / Raynet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 30},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_pipeline_velocity),
    },
    "get_project_throughput": {
        "description": (
            "Latest project / delivery throughput — open / overdue / "
            "completed item counts, activity volume, top boards. "
            "Source-agnostic across Trello / Asana / Jira / Basecamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
            },
            "additionalProperties": False,
        },
        "invoke": _wrap(get_project_throughput),
    },
    "search_company_knowledge": {
        "description": (
            "Semantic search over the indexed Workspace knowledge base "
            "(Drive / Gmail / Calendar via the DWD connector). Returns the "
            "top-K matching chunks with citations. Use when the user asks "
            "for facts that should live in company documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
                "source": {"type": "string", "enum": ["drive", "gmail", "calendar"]},
                "owner_email": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "invoke": _wrap(search_company_knowledge),
    },
}


def anthropic_tool_specs(names: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    """Return the Anthropic-shaped tool list for the requested names."""
    out: list[dict[str, Any]] = []
    for name in names:
        spec = TOOLS.get(name)
        if not spec:
            raise KeyError(f"Unknown agent tool: {name!r}")
        out.append(
            {
                "name": name,
                "description": spec["description"],
                "input_schema": spec["input_schema"],
            }
        )
    return out


def invoke_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Execute a registered tool and return a JSON-string result for the model."""
    spec = TOOLS.get(name)
    if not spec:
        return json.dumps({"ok": False, "error": "unknown_tool", "tool": name})
    return json.dumps(spec["invoke"](**(arguments or {})), default=str)
