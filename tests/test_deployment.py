"""Deployment-related tests: health endpoint + production-settings hardening."""

from __future__ import annotations

import importlib
import sys

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_endpoint(client: Client) -> None:
    """``/health/`` must return 200 without auth."""
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_production_settings_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loading ``config.settings.production`` enables core security flags."""
    monkeypatch.setenv("SECRET_KEY", "test-prod-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://x:y@localhost:5432/z")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)

    sys.modules.pop("config.settings.production", None)
    sys.modules.pop("config.settings.base", None)
    production = importlib.import_module("config.settings.production")

    assert production.DEBUG is False
    assert production.SECURE_SSL_REDIRECT is True
    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.SECURE_HSTS_SECONDS >= 31536000
    assert production.X_FRAME_OPTIONS == "DENY"
    assert ".sentinex.io" in production.ALLOWED_HOSTS
    assert production.STATIC_ROOT == "/app/staticfiles"
    assert production.MEDIA_ROOT == "/app/media"
