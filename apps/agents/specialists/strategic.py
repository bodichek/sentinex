"""Strategic specialist — high-level positioning and risk analysis."""

from __future__ import annotations

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse


class StrategicSpecialist(BaseSpecialist):
    name = "strategic"
    system_prompt_file = "strategic_specialist"
    model = "sonnet"

    # Strategic owns the wide-angle view: weekly pulse, anomalies, finance,
    # marketing, sales, projects, plus Knowledge RAG for grounded facts.
    tool_names = (
        "get_weekly_metrics",
        "get_recent_anomalies",
        "get_team_activity_summary",
        "get_cashflow_snapshot",
        "get_marketing_funnel",
        "get_pipeline_velocity",
        "get_project_throughput",
        "search_company_knowledge",
    )

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        return self._default_analyze(context)
