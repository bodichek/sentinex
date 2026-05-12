"""URL config for the memory module."""

from __future__ import annotations

from django.urls import path

from apps.memory.views import (
    MemoryEntitiesView,
    MemoryEntityDeleteView,
    MemoryEpisodeView,
    MemorySearchView,
)

urlpatterns = [
    path("memory/search/", MemorySearchView.as_view(), name="api_memory_search"),
    path("memory/entities/", MemoryEntitiesView.as_view(), name="api_memory_entities"),
    path("memory/episode/", MemoryEpisodeView.as_view(), name="api_memory_episode"),
    path(
        "memory/entity/<str:entity_uuid>/",
        MemoryEntityDeleteView.as_view(),
        name="api_memory_entity_delete",
    ),
]
