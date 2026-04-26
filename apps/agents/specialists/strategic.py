"""Strategic specialist — high-level positioning and risk analysis."""

from __future__ import annotations

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse


class StrategicSpecialist(BaseSpecialist):
    name = "strategic"
    system_prompt_file = "strategic_specialist"
    model = "sonnet"

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        return self._default_analyze(context)
