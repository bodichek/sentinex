from __future__ import annotations

from django.urls import path

from apps.connectors.hubspot import views

app_name = "connectors_hubspot"

urlpatterns = [
    path("connect/", views.connect, name="connect"),
    path("callback/", views.callback, name="callback"),
]
