"""Chat views: list, detail, send-message, new-conversation."""

from __future__ import annotations

import logging
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.agents import context_builder, orchestrator
from apps.chat.models import Conversation, Message
from apps.core.middleware import require_membership

logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 10
LTM_TOP_K = 3
ERROR_FALLBACK = "Omlouvám se, nastala chyba. Zkuste to znovu."


@login_required
@require_membership
def chat_list(request: HttpRequest) -> HttpResponse:
    conversations = Conversation.objects.filter(user_id=request.user.pk)
    return render(request, "chat/chat_list.html", {"conversations": conversations})


@login_required
@require_membership
def chat_detail(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, user_id=request.user.pk
    )
    messages = list(conversation.messages.all())
    return render(
        request,
        "chat/chat_detail.html",
        {"conversation": conversation, "chat_messages": messages},
    )


@login_required
@require_membership
@require_POST
def new_conversation(request: HttpRequest) -> HttpResponse:
    conversation = Conversation.objects.create(user_id=request.user.pk, title="Nový chat")
    return redirect("chat:detail", conversation_id=conversation.id)


@login_required
@require_membership
@require_POST
def send_message(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, user_id=request.user.pk
    )
    content = (request.POST.get("content") or "").strip()
    if not content:
        return redirect("chat:detail", conversation_id=conversation.id)

    Message.objects.create(conversation=conversation, role=Message.ROLE_USER, content=content)
    if conversation.title in ("", "Nový chat"):
        conversation.title = _title_from(content)
    conversation.save(update_fields=["title", "updated_at"])

    assistant_text = _run_agent(content, conversation)
    Message.objects.create(
        conversation=conversation, role=Message.ROLE_ASSISTANT, content=assistant_text
    )
    conversation.save(update_fields=["updated_at"])
    return redirect("chat:detail", conversation_id=conversation.id)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _title_from(text: str) -> str:
    words = text.split()[:10]
    return " ".join(words)[:200] or "Nový chat"


def _run_agent(query: str, conversation: Conversation) -> str:
    try:
        history = list(conversation.messages.order_by("-created_at")[:CONTEXT_WINDOW])
        history.reverse()
        history_lines = [f"{m.role}: {m.content}" for m in history]

        memory_lines: list[str] = []
        try:
            from apps.agents.memory import LongTermMemory

            results = LongTermMemory().search(query, top_k=LTM_TOP_K)
            memory_lines = [f"- ({r.source}) {r.content[:300]}" for r in results]
        except Exception:
            logger.exception("LongTermMemory search failed; continuing without RAG")

        ctx = context_builder.build(query)
        extra = dict(ctx.extra)
        extra["conversation_history"] = history_lines
        extra["long_term_memory"] = memory_lines
        from apps.agents.base import AgentContext

        ctx = AgentContext(
            query=ctx.query,
            tenant_schema=ctx.tenant_schema,
            org_summary=ctx.org_summary,
            extra=extra,
        )

        response = orchestrator.handle(query, ctx)
        return response.final or ERROR_FALLBACK
    except Exception:
        logger.exception("orchestrator failed in chat send_message")
        return ERROR_FALLBACK
