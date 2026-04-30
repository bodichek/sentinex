"""Raynet setup wizard — paste instance + username + API key."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.raynet.client import RaynetClient
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


@login_required
@require_membership
@require_admin
def setup(request: HttpRequest) -> HttpResponse:
    integration = Integration.objects.filter(provider="raynet").first()
    return render(request, "connectors/raynet_setup.html", {"integration": integration})


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    instance = (request.POST.get("instance") or "").strip()
    username = (request.POST.get("username") or "").strip()
    api_key = (request.POST.get("api_key") or "").strip()
    if not (instance and username and api_key):
        return render(
            request,
            "connectors/raynet_setup.html",
            {"error": "Vyplň všechny tři údaje (instance, username, API key)."},
            status=400,
        )

    integration, _ = Integration.objects.get_or_create(provider="raynet")
    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"instance": instance, "username": username, "api_key": api_key})
    credential.save()

    try:
        with RaynetClient(integration) as client:
            client.ping()
    except Exception as exc:
        return render(
            request,
            "connectors/raynet_setup.html",
            {"error": f"Ověření selhalo: {exc}"},
            status=400,
        )

    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])
    return redirect("list_integrations")
