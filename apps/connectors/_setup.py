"""Shared helpers for paste-key setup wizards.

Every paste-key connector (SmartEmailing, Trello, Raynet, Caflou, Ecomail,
FAPI) follows the same retry contract:

- The save view tries the credential by pinging the upstream API.
- On failure: persist a structured ``last_setup`` record into
  ``Integration.meta`` so the wizard can render an ISO-timestamped error
  on next render. Non-secret form values (username, instance, e-mail) are
  echoed back into the form to spare the user re-typing. Secret fields
  (api_key, token, password) are **never** persisted to meta and are not
  echoed back into the form.
- On success: clear ``last_setup`` and flip ``is_active=True`` /
  ``connected_at=now``.

The wizard also exposes a ``reset`` action — POST to
``/integrations/<provider>/reset/`` clears the last_setup banner so the
user can start over with a clean slate.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.data_access.models import Integration


def record_setup_attempt(
    integration: Integration,
    *,
    fields: dict[str, str] | None = None,
    error: str | None = None,
) -> None:
    """Persist a non-secret summary of the last setup attempt.

    ``fields`` MUST exclude every secret (api_key, token, password). The
    helper does not enforce this — the caller is responsible for filtering.
    """
    meta = dict(integration.meta or {})
    meta["last_setup"] = {
        "fields": fields or {},
        "error": error,
        "at": timezone.now().isoformat(),
    }
    integration.meta = meta
    integration.save(update_fields=["meta"])


def clear_setup_attempt(integration: Integration) -> None:
    meta = dict(integration.meta or {})
    meta.pop("last_setup", None)
    integration.meta = meta
    integration.save(update_fields=["meta"])


def last_setup_context(integration: Integration | None) -> dict[str, Any]:
    """Build the template context fragment from a saved last_setup record."""
    if integration is None:
        return {"last_error": "", "last_at": "", "last_fields": {}}
    record = (integration.meta or {}).get("last_setup") or {}
    return {
        "last_error": record.get("error") or "",
        "last_at": record.get("at") or "",
        "last_fields": record.get("fields") or {},
    }
