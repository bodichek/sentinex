from __future__ import annotations

from django.urls import path

from apps.connectors.fapi import views

app_name = "connectors_fapi"

urlpatterns = [
    path("setup/", views.setup, name="setup"),
    path("save/", views.save_credentials, name="save"),
]
