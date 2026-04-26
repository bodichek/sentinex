"""Decorators for addon-gated views."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse

from apps.core.feature_flags import is_enabled


def addon_required(addon_name: str) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    def decorator(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            tenant = getattr(request, "tenant", None)
            if tenant is None or not is_enabled(tenant, addon_name):
                raise Http404("Addon not available")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
