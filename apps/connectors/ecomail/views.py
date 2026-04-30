from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.ecomail.client import EcomailClient
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


@login_required
@require_membership
@require_admin
def setup(request: HttpRequest) -> HttpResponse:
    integration = Integration.objects.filter(provider="ecomail").first()
    return render(request, "connectors/ecomail_setup.html", {"integration": integration})


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    api_key = (request.POST.get("api_key") or "").strip()
    if not api_key:
        return render(
            request,
            "connectors/ecomail_setup.html",
            {"error": "Vyplň API klíč."},
            status=400,
        )

    integration, _ = Integration.objects.get_or_create(provider="ecomail")
    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"api_key": api_key})
    credential.save()

    try:
        with EcomailClient(integration) as client:
            client.ping()
    except Exception as exc:
        return render(
            request,
            "connectors/ecomail_setup.html",
            {"error": f"Ověření selhalo: {exc}"},
            status=400,
        )

    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])
    return redirect("list_integrations")
