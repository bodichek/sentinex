from __future__ import annotations

from django.urls import path

from apps.data_access import views

urlpatterns = [
    path("", views.list_integrations, name="list_integrations"),
    path(
        "google_workspace/connect/",
        views.connect_google_workspace,
        name="connect_google_workspace",
    ),
    path(
        "google_workspace/callback/",
        views.google_workspace_callback,
        name="google_workspace_callback",
    ),
    path("<str:provider>/disconnect/", views.disconnect, name="disconnect_integration"),
]


insights_urlpatterns = (
    [
        path("", views.insights_index, name="index"),
        path("cards/<str:name>/", views.insight_card, name="card"),
    ],
    "insights",
)
