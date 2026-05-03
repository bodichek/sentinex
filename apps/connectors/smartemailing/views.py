"""Setup wizard for SmartEmailing — paste username + API key."""

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
from apps.connectors.smartemailing.client import SmartEmailingClient
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


@login_required
@require_membership
@require_admin
def setup(request: HttpRequest) -> HttpResponse:
    integration = Integration.objects.filter(provider="smartemailing").first()
    return render(
        request,
        "connectors/smartemailing_setup.html",
        {"integration": integration, **last_setup_context(integration)},
    )


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    username = (request.POST.get("username") or "").strip()
    api_key = (request.POST.get("api_key") or "").strip()
    integration, _ = Integration.objects.get_or_create(provider="smartemailing")

    if not username or not api_key:
        record_setup_attempt(
            integration, fields={"username": username}, error="Vyplň username i API key."
        )
        return render(
            request,
            "connectors/smartemailing_setup.html",
            {
                "integration": integration,
                "error": "Vyplň username i API key.",
                **last_setup_context(integration),
            },
            status=400,
        )

    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"username": username, "api_key": api_key})
    credential.save()

    try:
        with SmartEmailingClient(integration) as client:
            client.ping()
    except Exception as exc:
        record_setup_attempt(
            integration, fields={"username": username}, error=f"Ověření selhalo: {exc}"
        )
        return render(
            request,
            "connectors/smartemailing_setup.html",
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
