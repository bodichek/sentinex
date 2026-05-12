"""Django app config for the memory module."""

from __future__ import annotations

from django.apps import AppConfig


class MemoryConfig(AppConfig):
    name = "apps.memory"
    label = "memory"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Sentinex Memory (Graphiti)"
