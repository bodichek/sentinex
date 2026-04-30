"""Knowledge specialist — answers from indexed Workspace documents (RAG)."""

from __future__ import annotations

from apps.agents.base import AgentContext, BaseSpecialist, SpecialistResponse
from apps.agents.guardrails import check_scope, mask_pii
from apps.agents.llm_gateway import complete
from apps.agents.prompt_loader import load_prompt


class KnowledgeSpecialist(BaseSpecialist):
    """Retrieval-Augmented specialist — searches the company knowledge index
    (Drive/Gmail/Calendar via DWD) and answers with citations."""

    name = "knowledge"
    system_prompt_file = "knowledge_specialist"
    model = "sonnet"
    temperature = 0.2
    max_tokens = 1500
    top_k = 8

    def analyze(self, context: AgentContext) -> SpecialistResponse:
        scope = check_scope(self.name, "analyze")
        if not scope.ok:
            return SpecialistResponse(
                name=self.name, content=f"scope rejected: {scope.reason}", confidence=0.0
            )

        # Late import — search depends on pgvector + tenant schema being set
        from apps.data_access.insight_functions.knowledge import search_company_knowledge

        ctx = search_company_knowledge(query=context.query, top_k=self.top_k)

        if not ctx.hits:
            return SpecialistResponse(
                name=self.name,
                content=(
                    "K této otázce nemám ve firemních dokumentech žádný relevantní podklad. "
                    "Buď index zatím není naplněný, nebo dotaz mimo dosah indexovaných zdrojů."
                ),
                structured_data={"hits": [], "query": context.query},
                confidence=0.2,
            )

        # Mask PII in retrieved chunks before they enter the LLM prompt.
        masked_context = mask_pii(ctx.prompt_context).text

        system = load_prompt(self.system_prompt_file)
        user_prompt = (
            f"Otázka uživatele:\n{context.query}\n\n"
            f"Kontext z firemních dokumentů (citace [1], [2], ...):\n\n"
            f"{masked_context}\n\n"
            "Odpověz výhradně na základě tohoto kontextu. Pokud kontext nestačí, "
            "řekni to. Cituj zdroje pomocí [1], [2], atd."
        )
        response = complete(
            user_prompt,
            model=self.model,
            system=system,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return SpecialistResponse(
            name=self.name,
            content=response.content,
            structured_data={
                "query": context.query,
                "hits": ctx.hits,
                "citation_count": len(ctx.hits),
            },
            usage=response,
        )
