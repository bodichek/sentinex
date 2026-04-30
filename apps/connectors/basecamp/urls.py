from __future__ import annotations

from django.urls import path

from apps.connectors.basecamp import views

app_name = "connectors_basecamp"

urlpatterns = [
    path("connect/", views.connect, name="connect"),
    path("callback/", views.callback, name="callback"),
]
