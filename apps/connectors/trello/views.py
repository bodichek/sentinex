"""Trello setup wizard — paste API key + token."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
        {"integration": integration},
    )


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    api_key = (request.POST.get("api_key") or "").strip()
    token = (request.POST.get("token") or "").strip()
    if not api_key or not token:
        return render(
            request,
            "connectors/trello_setup.html",
            {"error": "Vyplň API key i token."},
            status=400,
        )

    integration, _ = Integration.objects.get_or_create(provider="trello")
    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"api_key": api_key, "token": token})
    credential.save()

    try:
        with TrelloClient(integration) as client:
            client.me()
    except Exception as exc:
        return render(
            request,
            "connectors/trello_setup.html",
            {"error": f"Ověření selhalo: {exc}"},
            status=400,
        )

    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])
    return redirect("list_integrations")
