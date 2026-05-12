"""Analytics URL config."""

from __future__ import annotations

from django.urls import path

from apps.analytics.views import CostsView, RunsView, UsageView

urlpatterns = [
    path("analytics/usage/", UsageView.as_view(), name="api_analytics_usage"),
    path("analytics/runs/", RunsView.as_view(), name="api_analytics_runs"),
    path("analytics/costs/", CostsView.as_view(), name="api_analytics_costs"),
]
