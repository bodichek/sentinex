from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.caflou.client import CaflouClient
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


@login_required
@require_membership
@require_admin
def setup(request: HttpRequest) -> HttpResponse:
    integration = Integration.objects.filter(provider="caflou").first()
    return render(request, "connectors/caflou_setup.html", {"integration": integration})


@login_required
@require_membership
@require_admin
@require_POST
def save_credentials(request: HttpRequest) -> HttpResponse:
    api_token = (request.POST.get("api_token") or "").strip()
    if not api_token:
        return render(
            request,
            "connectors/caflou_setup.html",
            {"error": "Vyplň API token."},
            status=400,
        )

    integration, _ = Integration.objects.get_or_create(provider="caflou")
    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens({"api_token": api_token})
    credential.save()

    try:
        with CaflouClient(integration) as client:
            client.ping()
    except Exception as exc:
        return render(
            request,
            "connectors/caflou_setup.html",
            {"error": f"Ověření selhalo: {exc}"},
            status=400,
        )

    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])
    return redirect("list_integrations")
