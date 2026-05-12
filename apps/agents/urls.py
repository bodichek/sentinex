"""Agent Layer URL config."""

from __future__ import annotations

from django.urls import path

from apps.agents.views import AgentRunView, QueryView

urlpatterns = [
    path("query/", QueryView.as_view(), name="api_query"),
    path("agents/<str:agent_type>/run/", AgentRunView.as_view(), name="api_agent_run"),
]
