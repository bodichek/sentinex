"""Addon discovery + registration + per-tenant activation hooks."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from django.apps import apps as django_apps

from apps.core.addons.manifest import AddonManifest

logger = logging.getLogger(__name__)


class AddonRegistry:
    """In-memory registry of discovered addons. Singleton via module-level ``registry``."""

    def __init__(self) -> None:
        self._manifests: dict[str, AddonManifest] = {}
        self._discovered = False

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------
    def discover(self, force: bool = False) -> None:
        if self._discovered and not force:
            return
        self._manifests.clear()
        for cfg in django_apps.get_app_configs():
            if not cfg.name.startswith("apps.addons."):
                continue
            module_name = f"{cfg.name}.manifest"
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError:
                logger.warning("Addon '%s' has no manifest.py", cfg.name)
                continue
            manifest = getattr(module, "manifest", None)
            if not isinstance(manifest, AddonManifest):
                logger.warning("Addon '%s' manifest is not AddonManifest", cfg.name)
                continue
            self._manifests[manifest.name] = manifest
        self._discovered = True

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def all(self) -> list[AddonManifest]:
        self.discover()
        return list(self._manifests.values())

    def get(self, name: str) -> AddonManifest | None:
        self.discover()
        return self._manifests.get(name)

    # ------------------------------------------------------------------
    # lifecycle hooks
    # ------------------------------------------------------------------
    def call_lifecycle(self, addon_name: str, hook: str, tenant: Any) -> None:
        self.discover()
        manifest = self._manifests.get(addon_name)
        if manifest is None:
            return
        cfg = next(
            (
                c
                for c in django_apps.get_app_configs()
                if c.name.startswith("apps.addons.") and c.name.endswith(f".{addon_name}")
            ),
            None,
        )
        if cfg is None:
            return
        func = getattr(cfg, hook, None)
        if callable(func):
            try:
                func(tenant)
            except Exception:
                logger.exception("Addon %s %s failed", addon_name, hook)


registry = AddonRegistry()
