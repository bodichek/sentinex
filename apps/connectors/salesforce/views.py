from __future__ import annotations

import secrets

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.salesforce import oauth
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


def _redirect_uri(request: HttpRequest) -> str:
    return request.build_absolute_uri("/integrations/salesforce/callback/")


@login_required
@require_membership
@require_admin
@require_POST
def connect(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(24)
    request.session["sf_oauth_state"] = state
    try:
        url = oauth.authorization_url(state, _redirect_uri(request))
    except RuntimeError as exc:
        return render(request, "integrations/connect.html", {"error": str(exc)}, status=400)
    return redirect(url)


@login_required
@require_membership
@require_admin
def callback(request: HttpRequest) -> HttpResponse:
    if (err := request.GET.get("error")):
        return render(request, "integrations/connect.html", {"error": err}, status=400)
    expected = request.session.pop("sf_oauth_state", None)
    if request.GET.get("state") != expected or not expected:
        return render(request, "integrations/connect.html", {"error": "Invalid OAuth state."}, status=400)
    code = request.GET.get("code", "")
    if not code:
        return render(request, "integrations/connect.html", {"error": "Missing code."}, status=400)

    tokens = oauth.exchange_code(code, _redirect_uri(request))

    integration, _ = Integration.objects.get_or_create(provider="salesforce")
    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.meta = {"instance_url": tokens.get("instance_url"), "scope": tokens.get("scope")}
    integration.save(update_fields=["is_active", "connected_at", "meta"])

    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens(tokens)
    credential.save()

    return redirect("list_integrations")
