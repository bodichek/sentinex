"""Weekly Brief event subscribers."""

from __future__ import annotations

from typing import Any

from django.dispatch import receiver

from apps.core.addons.events import data_synced


@receiver(data_synced)
def on_data_synced(sender: Any, **kwargs: Any) -> None:
    # Placeholder: could trigger brief regeneration on large data refreshes.
    return
