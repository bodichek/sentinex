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
    path("<str:provider>/reset/", views.reset_setup, name="reset_setup"),
    path(
        "google_workspace_dwd/setup/",
        views.workspace_dwd_setup,
        name="workspace_dwd_setup",
    ),
    path(
        "google_workspace_dwd/ingest/",
        views.workspace_dwd_ingest,
        name="workspace_dwd_ingest",
    ),
    path(
        "google_workspace_dwd/dashboard/",
        views.workspace_dwd_dashboard,
        name="workspace_dwd_dashboard",
    ),
]


insights_urlpatterns = (
    [
        path("", views.insights_index, name="index"),
        path("cards/<str:name>/", views.insight_card, name="card"),
    ],
    "insights",
)
