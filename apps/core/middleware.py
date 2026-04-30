"""Middleware enforcing tenant membership for authenticated requests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import resolve

from apps.core.models import Role, TenantMembership

PUBLIC_VIEW_NAMESPACES = {"account", "admin", "socialaccount"}
PUBLIC_PATH_PREFIXES = (
    "/accounts/",
    "/admin/",
    "/static/",
    "/media/",
    "/invitations/",
)


class TenantMembershipMiddleware:
    """Attach ``request.tenant_membership`` and enforce access.

    - Skipped on the public schema (landing / marketing).
    - Allowed for unauthenticated requests (allauth handles its own redirects).
    - For authenticated users on a tenant subdomain: requires membership.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def _is_public_path(self, request: HttpRequest) -> bool:
        if request.path.startswith(PUBLIC_PATH_PREFIXES):
            return True
        try:
            match = resolve(request.path)
        except Exception:
            return False
        return match.namespace in PUBLIC_VIEW_NAMESPACES

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.tenant_membership = None  # type: ignore[attr-defined]

        if connection.schema_name == settings.PUBLIC_SCHEMA_NAME:  # type: ignore[attr-defined]
            return self.get_response(request)

        if self._is_public_path(request):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return self.get_response(request)

        membership = TenantMembership.objects.filter(user=user, tenant=tenant).first()
        if membership is None:
            return redirect("no_membership")
        request.tenant_membership = membership  # type: ignore[attr-defined]
        return self.get_response(request)


def require_membership(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """View decorator: reject requests without a tenant membership."""

    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        membership = getattr(request, "tenant_membership", None)
        if membership is None:
            return redirect("no_membership")
        return view_func(request, *args, **kwargs)

    return wrapper


_ADMIN_ROLES = {Role.OWNER, Role.ADMIN}


def require_admin(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """View decorator: only Owner/Admin tenant members allowed.

    Used to gate destructive or high-cost actions (re-ingest, disconnect)
    so any seat holder cannot trigger them.
    """

    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        membership = getattr(request, "tenant_membership", None)
        if membership is None or membership.role not in _ADMIN_ROLES:
            return HttpResponse(status=403)
        return view_func(request, *args, **kwargs)

    return wrapper
