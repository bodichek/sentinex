"""URL config for observability."""

from __future__ import annotations

from django.urls import path

from apps.observability.views import TracesView

urlpatterns = [
    path("observability/traces/", TracesView.as_view(), name="api_observability_traces"),
]
