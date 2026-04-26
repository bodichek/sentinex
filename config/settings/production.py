"""Production settings — DJANGO_SETTINGS_MODULE=config.settings.production."""

from __future__ import annotations

from config.settings.base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False
ALLOWED_HOSTS = [".sentinex.io", "sentinex.io"]
CSRF_TRUSTED_ORIGINS = ["https://*.sentinex.io", "https://sentinex.io"]

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_ROOT = "/app/staticfiles"
MEDIA_ROOT = "/app/media"

# ---------------------------------------------------------------------------
# Logging — JSON to stdout, level INFO
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "config.logging.JsonFormatter",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "sentinex.llm": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "sentinex.agents": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
    },
}
