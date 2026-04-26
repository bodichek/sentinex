"""Orchestrator: classifies intent, fans out to specialists, composes reply."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from celery import group
from django.conf import settings

from apps.agents.base import AgentContext, SpecialistResponse
from apps.agents.guardrails import (
    detect_prompt_injection,
    log_for_compliance,
    mask_pii,
    unmask_pii,
    validate_output_format,
)
from apps.agents.llm_gateway import complete
from apps.agents.prompt_loader import load_prompt
from apps.agents.specialists import REGISTRY
from apps.agents.tasks import run_specialist

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Intent:
    intent: str
    summary: str
    required_specialists: list[str]
    reasoning: str = ""


@dataclass(frozen=True)
class OrchestratorResponse:
    intent: Intent
    specialist_responses: list[SpecialistResponse] = field(default_factory=list)
    final: str = ""


class Orchestrator:
    """Entry point for every user query."""

    model = "sonnet"
    temperature = 0.0

    def classify_intent(self, query: str) -> Intent:
        system = load_prompt("orchestrator")
        raw = complete(
            f"Question: {query}",
            model=self.model,
            system=system,
            temperature=self.temperature,
            max_tokens=512,
        ).content
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Orchestrator returned non-JSON: {raw[:200]}") from exc

        required = [s for s in data.get("required_specialists", []) if s in REGISTRY]
        return Intent(
            intent=str(data.get("intent", "unknown")),
            summary=str(data.get("summary", query)),
            required_specialists=required,
            reasoning=str(data.get("reasoning", "")),
        )

    def select_specialists(self, intent: Intent) -> list[str]:
        return intent.required_specialists

    def handle(self, query: str, context: AgentContext) -> OrchestratorResponse:
        # Pre-call guardrails: injection + PII masking
        injection = detect_prompt_injection(query)
        if not injection.ok:
            logger.warning("rejecting query: %s", injection.reason)
            return OrchestratorResponse(
                intent=Intent(intent="rejected", summary=injection.reason, required_specialists=[]),
                final="Dotaz byl zamítnut z bezpečnostních důvodů.",
            )

        masked = mask_pii(query)
        safe_query = masked.text
        safe_context = AgentContext(
            query=safe_query,
            tenant_schema=context.tenant_schema,
            org_summary=context.org_summary,
            extra=context.extra,
        )

        intent = self.classify_intent(safe_query)
        names = self.select_specialists(intent)

        specialist_responses: list[SpecialistResponse] = []
        if names:
            specialist_responses = self._run_specialists(names, safe_context)

        masked_final = self._compose(safe_query, intent, specialist_responses)

        # Post-call guardrails: validate + unmask + compliance log
        validation = validate_output_format(masked_final)
        if not validation.ok:
            logger.warning("output validation failed: %s", validation.reason)

        final = unmask_pii(masked_final, masked.mask_map)

        log_for_compliance(
            tenant=getattr(context, "tenant", None),
            user=None,
            agent="orchestrator",
            model=self.model,
            prompt=query,
            response=final,
            success=validation.ok,
            error=validation.reason,
        )

        return OrchestratorResponse(
            intent=intent, specialist_responses=specialist_responses, final=final
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _run_specialists(
        self, names: list[str], context: AgentContext
    ) -> list[SpecialistResponse]:
        ctx_dict = asdict(context)

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            # Tests / dev: run synchronously without a live worker.
            raw_results = [run_specialist.run(n, ctx_dict) for n in names]
        else:
            job = group(run_specialist.s(n, ctx_dict) for n in names).apply_async()
            raw_results = job.get(timeout=120)

        responses: list[SpecialistResponse] = []
        for r in raw_results:
            responses.append(
                SpecialistResponse(
                    name=r["name"],
                    content=r["content"],
                    structured_data=r.get("structured_data") or {},
                    confidence=r.get("confidence", 1.0),
                )
            )
        return responses

    def _compose(
        self, query: str, intent: Intent, specialists: list[SpecialistResponse]
    ) -> str:
        if not specialists:
            response = complete(
                f"Answer concisely in the user's language: {query}",
                model=self.model,
                temperature=0.3,
                max_tokens=512,
            )
            return response.content

        blocks = "\n\n".join(
            f"### {s.name}\n{s.content}" for s in specialists
        )
        system = (
            "You are Sentinex. Synthesize the specialists below into one concise "
            "answer for the user. Preserve concrete numbers and recommendations. "
            "Do not add meta commentary. Default to the user's language (often Czech)."
        )
        user_prompt = f"User question: {query}\n\nIntent: {intent.summary}\n\nSpecialist reports:\n{blocks}"
        response = complete(
            user_prompt,
            model=self.model,
            system=system,
            temperature=0.3,
            max_tokens=1024,
        )
        return response.content


def handle(query: str, context: AgentContext) -> OrchestratorResponse:
    """Module-level convenience wrapper."""
    return Orchestrator().handle(query, context)
