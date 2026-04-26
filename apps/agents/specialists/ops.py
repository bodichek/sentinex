"""Ops specialist — reliability, deployments, incidents, infra cost, tech debt."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse

logger = logging.getLogger(__name__)


class OpsAnalysis(BaseModel):
    """Structured output from OpsSpecialist."""

    reliability_score: float = Field(ge=0.0, le=1.0)
    deployment_health: Literal["healthy", "degraded", "critical"]
    incidents: list[str] = Field(default_factory=list)
    cost_trend: Literal["stable", "rising", "falling"]
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class OpsSpecialist(BaseSpecialist):
    name = "ops"
    system_prompt_file = "ops_specialist"
    model = "sonnet"

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        base = self._default_analyze(context)
        analysis = self._parse(base.content)
        structured = analysis.model_dump() if analysis is not None else {}
        confidence = analysis.confidence if analysis is not None else 0.0
        return SpecialistResponse(
            name=self.name,
            content=base.content,
            structured_data=structured,
            confidence=confidence,
            usage=base.usage,
        )

    @staticmethod
    def _parse(raw: str) -> OpsAnalysis | None:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("OpsSpecialist: non-JSON LLM output")
            return None
        try:
            return OpsAnalysis.model_validate(data)
        except ValidationError as exc:
            logger.warning("OpsSpecialist: schema validation failed: %s", exc)
            return None
