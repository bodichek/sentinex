"""Registry-level invariants for every shipped connector.

Catches the most common wiring bugs (missing import in registry,
provider-name mismatch, forgotten Integration.PROVIDER_CHOICES entry)
in a single test that grows automatically as we add connectors.
"""

from __future__ import annotations

from apps.data_access.mcp.registry import default_integrations
from apps.data_access.models import Integration


def test_registry_provider_names_match_classes() -> None:
    integrations = default_integrations()
    for key, integration in integrations.items():
        assert (
            integration.provider == key
        ), f"registry key {key!r} != provider {integration.provider!r}"


def test_every_registered_provider_is_in_choices() -> None:
    keys = set(default_integrations().keys())
    choices = {k for k, _ in Integration.PROVIDER_CHOICES}
    missing = keys - choices
    assert not missing, f"providers wired in registry but not in PROVIDER_CHOICES: {missing}"


def test_every_provider_choice_is_wired() -> None:
    keys = set(default_integrations().keys())
    choices = {k for k, _ in Integration.PROVIDER_CHOICES}
    orphans = choices - keys
    assert not orphans, f"providers in PROVIDER_CHOICES but not wired in registry: {orphans}"


def test_integration_classes_implement_full_mcp_interface() -> None:
    required = ("authorization_url", "exchange_code", "refresh_tokens", "call")
    for key, integration in default_integrations().items():
        for name in required:
            assert callable(
                getattr(integration, name, None)
            ), f"connector {key} missing {name}"
