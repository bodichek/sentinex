"""Agent Layer URL config."""

from __future__ import annotations

from django.urls import path

from apps.agents.views import QueryView

urlpatterns = [
    path("query/", QueryView.as_view(), name="api_query"),
]
