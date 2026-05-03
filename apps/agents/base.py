"""Base classes for specialist agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from apps.agents.llm_gateway import LLMResponse, complete, complete_with_tools
from apps.agents.prompt_loader import load_prompt
from apps.agents.tools import anthropic_tool_specs, invoke_tool


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

    # Opt-in tool use. Subclasses set this to a tuple of tool names from
    # ``apps.agents.tools.TOOLS`` to let the model call insight functions
    # iteratively. Empty → falls back to a single-shot ``complete`` call.
    tool_names: tuple[str, ...] = ()
    max_tool_iterations: int = 6

    @abstractmethod
    def analyze(self, context: AgentContext) -> SpecialistResponse: ...

    # Default helper — subclasses usually just call super().analyze.
    def _default_analyze(self, context: AgentContext) -> SpecialistResponse:
        if self.tool_names:
            return self._tool_using_analyze(context)
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

    def _tool_using_analyze(self, context: AgentContext) -> SpecialistResponse:
        system = load_prompt(self.system_prompt_file)
        user = self._render_user_prompt(context)
        tools = anthropic_tool_specs(self.tool_names)
        result = complete_with_tools(
            user,
            tools=tools,
            invoke=invoke_tool,
            model=self.model,
            system=system,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_iterations=self.max_tool_iterations,
        )
        # Surface the tool trace in structured_data so the orchestrator and
        # compliance log see exactly which insight functions were called.
        trace = [
            {"name": tc.name, "arguments": tc.arguments, "result": tc.result}
            for tc in result.tool_calls
        ]
        return SpecialistResponse(
            name=self.name,
            content=result.content,
            structured_data={
                "tool_calls": trace,
                "iterations": result.iterations,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )

    def _render_user_prompt(self, context: AgentContext) -> str:
        parts = [f"User query: {context.query}"]
        if context.org_summary:
            parts.append(f"Organization: {context.org_summary}")
        if context.extra:
            parts.append(f"Additional context: {context.extra}")
        return "\n\n".join(parts)
