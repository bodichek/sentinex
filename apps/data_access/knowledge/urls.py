"""URL routing for knowledge search UI."""

from __future__ import annotations

from django.urls import path

from apps.data_access.knowledge import views

urlpatterns = [
    path("", views.knowledge_search, name="knowledge_search"),
]
