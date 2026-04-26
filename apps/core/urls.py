"""Core URL patterns."""

from __future__ import annotations

from django.urls import path

from apps.core import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("no-membership/", views.no_membership, name="no_membership"),
    path("invitations/<str:token>/", views.accept_invitation, name="accept_invitation"),
]
