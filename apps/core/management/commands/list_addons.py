"""List all discovered addons."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.core.addons import registry


class Command(BaseCommand):
    help = "List all discovered addons from INSTALLED_APPS."

    def handle(self, *args: Any, **opts: Any) -> None:
        registry.discover(force=True)
        addons = registry.all()
        if not addons:
            self.stdout.write(self.style.WARNING("No addons discovered."))
            return
        for m in addons:
            self.stdout.write(f"{m.name:<30} v{m.version:<10} {m.display_name}")
