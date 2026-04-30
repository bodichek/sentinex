from __future__ import annotations

import secrets

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.connectors.dropbox import oauth
from apps.connectors.dropbox.client import list_tools
from apps.core.middleware import require_admin, require_membership
from apps.data_access.models import Credential, Integration


def _redirect_uri(request: HttpRequest) -> str:
    return request.build_absolute_uri("/integrations/dropbox/callback/")


@login_required
@require_membership
@require_admin
@require_POST
def connect(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(24)
    verifier, challenge = oauth.generate_pkce_pair()
    request.session["dropbox_oauth_state"] = state
    request.session["dropbox_pkce_verifier"] = verifier
    try:
        url = oauth.authorization_url(state, _redirect_uri(request), challenge)
    except RuntimeError as exc:
        return render(request, "integrations/connect.html", {"error": str(exc)}, status=400)
    return redirect(url)


@login_required
@require_membership
@require_admin
def callback(request: HttpRequest) -> HttpResponse:
    if (err := request.GET.get("error")):
        return render(request, "integrations/connect.html", {"error": err}, status=400)
    expected = request.session.pop("dropbox_oauth_state", None)
    verifier = request.session.pop("dropbox_pkce_verifier", None)
    if request.GET.get("state") != expected or not expected or not verifier:
        return render(
            request,
            "integrations/connect.html",
            {"error": "Invalid OAuth state or missing PKCE verifier."},
            status=400,
        )
    code = request.GET.get("code", "")
    if not code:
        return render(request, "integrations/connect.html", {"error": "Missing code."}, status=400)

    tokens = oauth.exchange_code(code, _redirect_uri(request), verifier)
    integration, _ = Integration.objects.get_or_create(provider="dropbox")
    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    tools_meta: list[dict[str, str]] = []
    try:
        tools_meta = list_tools(tokens["access_token"])
    except Exception:
        tools_meta = []
    integration.meta = {
        "scope": tokens.get("scope"),
        "account_id": tokens.get("account_id"),
        "tools": tools_meta,
    }
    integration.save(update_fields=["is_active", "connected_at", "meta"])
    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens(tokens)
    credential.save()
    return redirect("list_integrations")
