"""Base classes for specialist agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from apps.agents.llm_gateway import LLMResponse, complete
from apps.agents.prompt_loader import load_prompt


@dataclass(frozen=True)
class AgentContext:
    """Input context passed to specialists and the orchestrator."""

    query: str
    tenant_schema: str | None = None
    org_summary: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpecialistResponse:
    name: str
    content: str
    structured_data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    usage: LLMResponse | None = None


class BaseSpecialist(ABC):
    """Abstract specialist. Subclasses define ``name`` + ``system_prompt_file``."""

    name: str = ""
    system_prompt_file: str = ""
    model: str = "sonnet"
    temperature: float = 0.3
    max_tokens: int = 2048

    @abstractmethod
    def analyze(self, context: AgentContext) -> SpecialistResponse: ...

    # Default helper — subclasses usually just call super().analyze.
    def _default_analyze(self, context: AgentContext) -> SpecialistResponse:
        system = load_prompt(self.system_prompt_file)
        user = self._render_user_prompt(context)
        response = complete(
            user,
            model=self.model,
            system=system,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return SpecialistResponse(name=self.name, content=response.content, usage=response)

    def _render_user_prompt(self, context: AgentContext) -> str:
        parts = [f"User query: {context.query}"]
        if context.org_summary:
            parts.append(f"Organization: {context.org_summary}")
        if context.extra:
            parts.append(f"Additional context: {context.extra}")
        return "\n\n".join(parts)
