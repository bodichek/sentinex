"""Finance specialist — cashflow, revenue, cost structure."""

from __future__ import annotations

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse


class FinanceSpecialist(BaseSpecialist):
    name = "finance"
    system_prompt_file = "finance_specialist"
    model = "sonnet"

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        return self._default_analyze(context)
