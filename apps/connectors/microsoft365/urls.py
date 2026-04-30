from __future__ import annotations

from django.urls import path

from apps.connectors.microsoft365 import views

app_name = "connectors_microsoft365"

urlpatterns = [
    path("connect/", views.connect, name="connect"),
    path("callback/", views.callback, name="callback"),
]
