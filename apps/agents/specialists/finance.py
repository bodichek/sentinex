"""Finance specialist — cashflow, revenue, cost structure."""

from __future__ import annotations

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse


class FinanceSpecialist(BaseSpecialist):
    name = "finance"
    system_prompt_file = "finance_specialist"
    model = "sonnet"

    # Finance pulls cashflow plus revenue-shaping signals (marketing funnel
    # + pipeline velocity) so it can comment on top-of-funnel and pipeline
    # quality, not just bank balance.
    tool_names = (
        "get_cashflow_snapshot",
        "get_marketing_funnel",
        "get_pipeline_velocity",
    )

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        return self._default_analyze(context)
