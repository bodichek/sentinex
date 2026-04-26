"""Core views: dashboard, membership errors, invitation accept."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.middleware import require_membership
from apps.core.models import Invitation


@login_required
@require_membership
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "core/dashboard.html",
        {"membership": request.tenant_membership, "tenant": request.tenant},  # type: ignore[attr-defined]
    )


def no_membership(request: HttpRequest) -> HttpResponse:
    return render(request, "core/no_membership.html", status=403)


def accept_invitation(request: HttpRequest, token: str) -> HttpResponse:
    invitation = get_object_or_404(Invitation, token=token, accepted_at__isnull=True)

    if not request.user.is_authenticated:
        request.session["pending_invitation_token"] = token
        return redirect(f"/accounts/signup/?email={invitation.email}")

    if request.user.email.lower() != invitation.email.lower():
        return render(
            request,
            "core/invitation_mismatch.html",
            {"invitation": invitation},
            status=403,
        )

    with transaction.atomic():
        invitation.accept(request.user)
    return redirect("dashboard")
