"""Views for the Integrations UI + OAuth flow + Insights dashboard."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.middleware import require_membership
from apps.data_access.insight_functions import (
    get_cashflow_snapshot,
    get_team_activity_summary,
    get_weekly_metrics,
)
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.mcp.integrations.google_workspace import GoogleWorkspaceIntegration
from apps.data_access.models import Credential, Integration


def _redirect_uri(request: HttpRequest, provider: str) -> str:
    return request.build_absolute_uri(f"/integrations/{provider}/callback/")


@login_required
@require_membership
def list_integrations(request: HttpRequest) -> HttpResponse:
    integrations = Integration.objects.all()
    return render(request, "integrations/list.html", {"integrations": integrations})


@login_required
@require_membership
@require_POST
def connect_google_workspace(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state

    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        return render(
            request, "integrations/connect.html",
            {"error": "GOOGLE_OAUTH_CLIENT_ID není nastavené v .env"}, status=400,
        )

    url = GoogleWorkspaceIntegration().authorization_url(
        state=state, redirect_uri=_redirect_uri(request, "google_workspace")
    )
    return redirect(url)


@login_required
@require_membership
def google_workspace_callback(request: HttpRequest) -> HttpResponse:
    error = request.GET.get("error")
    if error:
        return render(request, "integrations/connect.html", {"error": error}, status=400)

    expected_state = request.session.pop("google_oauth_state", None)
    if request.GET.get("state") != expected_state or not expected_state:
        return render(
            request, "integrations/connect.html", {"error": "Invalid OAuth state."}, status=400
        )

    code = request.GET.get("code", "")
    if not code:
        return render(
            request, "integrations/connect.html", {"error": "Missing code."}, status=400
        )

    tokens = GoogleWorkspaceIntegration().exchange_code(
        code=code, redirect_uri=_redirect_uri(request, "google_workspace")
    )

    integration, _ = Integration.objects.get_or_create(provider="google_workspace")
    integration.is_active = True
    integration.connected_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["is_active", "connected_at"])

    credential, _ = Credential.objects.get_or_create(integration=integration)
    credential.set_tokens(tokens)
    credential.save()

    return redirect("list_integrations")


@login_required
@require_membership
@require_POST
def disconnect(request: HttpRequest, provider: str) -> HttpResponse:
    Integration.objects.filter(provider=provider).update(is_active=False)
    return redirect("list_integrations")


# ---------------------------------------------------------------------------
# Insights dashboard (3 cards: Finance / People / Strategic)
# ---------------------------------------------------------------------------

_CARD_TEMPLATES = {
    "finance": "insights/_card_finance.html",
    "people": "insights/_card_people.html",
    "strategic": "insights/_card_strategic.html",
}

_CARD_FETCHERS: dict[str, Any] = {
    "finance": get_cashflow_snapshot,
    "people": get_team_activity_summary,
    "strategic": get_weekly_metrics,
}


def _load_card(name: str, *, refresh: bool = False) -> dict[str, Any]:
    fetcher = _CARD_FETCHERS[name]
    if refresh:
        # Bust the @cache_result wrapper by deleting its known cache prefix entries.
        # The decorator stores under "<key_prefix>:<args-hash>"; for our zero-arg
        # functions the suffix is stable, so a wildcard-free delete_pattern would
        # be needed. Instead, we just call through — fresh DB read every call is
        # cheap and aligns with explicit user intent.
        cache.clear()
    try:
        result = fetcher()
    except InsufficientData as exc:
        return {"name": name, "ok": False, "error": str(exc), "data": None}
    except Exception as exc:  # pragma: no cover — defensive
        return {"name": name, "ok": False, "error": f"failure: {exc}", "data": None}

    if hasattr(result, "__dataclass_fields__"):
        data: Any = asdict(result)
    elif isinstance(result, list):
        data = [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in result]
    else:
        data = result
    return {"name": name, "ok": True, "error": "", "data": data, "as_of": timezone.now()}


@login_required
@require_membership
def insights_index(request: HttpRequest) -> HttpResponse:
    cards = {name: _load_card(name) for name in _CARD_TEMPLATES}
    return render(request, "insights/index.html", {"cards": cards})


@login_required
@require_membership
def insight_card(request: HttpRequest, name: str) -> HttpResponse:
    if name not in _CARD_TEMPLATES:
        return HttpResponse(status=404)
    refresh = request.method == "POST" or request.GET.get("refresh") == "1"
    card = _load_card(name, refresh=refresh)
    return render(request, _CARD_TEMPLATES[name], {"card": card})
