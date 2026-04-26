"""People specialist — capacity, hiring, key-person risk, engagement signals."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse

logger = logging.getLogger(__name__)


class PeopleAnalysis(BaseModel):
    """Structured output from PeopleSpecialist."""

    capacity_score: float = Field(ge=0.0, le=1.0)
    hiring_health: Literal["healthy", "at_risk", "critical"]
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class PeopleSpecialist(BaseSpecialist):
    name = "people"
    system_prompt_file = "people_specialist"
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
    def _parse(raw: str) -> PeopleAnalysis | None:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("PeopleSpecialist: non-JSON LLM output")
            return None
        try:
            return PeopleAnalysis.model_validate(data)
        except ValidationError as exc:
            logger.warning("PeopleSpecialist: schema validation failed: %s", exc)
            return None
