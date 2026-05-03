"""Trello setup wizard — paste API key + token."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors._setup import (
    clear_setup_attempt,
    last_setup_context,
    record_setup_attempt,
)
from apps.connectors.trello.client import TrelloClient
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


@login_required
@require_membership
@require_admin
def setup(request: HttpRequest) -> HttpResponse:
    integration = Integration.objects.filter(provider="trello").first()
    return render(
        request,
        "connectors/trello_setup.html",
        {"integration": integration, **last_setup_context(integration)},
    )


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    api_key = (request.POST.get("api_key") or "").strip()
    token = (request.POST.get("token") or "").strip()
    integration, _ = Integration.objects.get_or_create(provider="trello")

    if not api_key or not token:
        record_setup_attempt(integration, fields={}, error="Vyplň API key i token.")
        return render(
            request,
            "connectors/trello_setup.html",
            {
                "integration": integration,
                "error": "Vyplň API key i token.",
                **last_setup_context(integration),
            },
            status=400,
        )

    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"api_key": api_key, "token": token})
    credential.save()

    try:
        with TrelloClient(integration) as client:
            client.me()
    except Exception as exc:
        record_setup_attempt(integration, fields={}, error=f"Ověření selhalo: {exc}")
        return render(
            request,
            "connectors/trello_setup.html",
            {
                "integration": integration,
                "error": f"Ověření selhalo: {exc}",
                **last_setup_context(integration),
            },
            status=400,
        )

    clear_setup_attempt(integration)
    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])
    return redirect("list_integrations")
