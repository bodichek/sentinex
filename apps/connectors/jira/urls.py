from __future__ import annotations

from django.urls import path

from apps.connectors.jira import views

app_name = "connectors_jira"

urlpatterns = [
    path("connect/", views.connect, name="connect"),
    path("callback/", views.callback, name="callback"),
]
