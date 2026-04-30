"""Pipedrive OAuth install + callback."""

from __future__ import annotations

import secrets

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.pipedrive.integration import PipedriveIntegration
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


def _redirect_uri(request: HttpRequest) -> str:
    return request.build_absolute_uri("/integrations/pipedrive/callback/")


@login_required
@require_membership
@require_admin
@require_POST
def connect(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(24)
    request.session["pipedrive_oauth_state"] = state
    try:
        url = PipedriveIntegration().authorization_url(state, _redirect_uri(request))
    except RuntimeError as exc:
        return render(
            request, "integrations/connect.html", {"error": str(exc)}, status=400
        )
    return redirect(url)


@login_required
@require_membership
@require_admin
def callback(request: HttpRequest) -> HttpResponse:
    error = request.GET.get("error")
    if error:
        return render(request, "integrations/connect.html", {"error": error}, status=400)

    expected = request.session.pop("pipedrive_oauth_state", None)
    if request.GET.get("state") != expected or not expected:
        return render(
            request, "integrations/connect.html", {"error": "Invalid OAuth state."}, status=400
        )

    code = request.GET.get("code", "")
    if not code:
        return render(request, "integrations/connect.html", {"error": "Missing code."}, status=400)

    tokens = PipedriveIntegration().exchange_code(code, _redirect_uri(request))

    integration, _ = Integration.objects.get_or_create(provider="pipedrive")
    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.meta = {
        "api_domain": tokens.get("api_domain"),
        "scope": tokens.get("scope"),
    }
    integration.save(update_fields=["is_active", "connected_at", "meta"])

    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens(tokens)
    credential.save()

    return redirect("list_integrations")
