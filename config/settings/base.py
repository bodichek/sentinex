"""Base Django settings shared across environments."""

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", ".sentinex.local"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SESSION_COOKIE_AGE=(int, 86400),
    LLM_CACHE_ENABLED=(bool, True),
    LLM_CACHE_DEFAULT_TTL=(int, 3600),
    USD_TO_CZK=(float, 24.0),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="insecure-dev-only-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

ROOT_URLCONF = "config.urls"
PUBLIC_SCHEMA_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Applications (django-tenants split)
# ---------------------------------------------------------------------------
SHARED_APPS = [
    "django_tenants",
    "apps.core",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "allauth",
    "allauth.account",
]

TENANT_APPS = [
    "apps.agents",
    "apps.data_access",
    "apps.chat",
    "apps.addons.weekly_brief",
]

INSTALLED_APPS = [*SHARED_APPS, *[a for a in TENANT_APPS if a not in SHARED_APPS]]

TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.core.middleware.TenantMembershipMiddleware",
]

# ---------------------------------------------------------------------------
# Auth / allauth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "core.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m"}

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"
ACCOUNT_LOGOUT_ON_GET = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# ---------------------------------------------------------------------------
# Database (django-tenants router)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        **env.db_url(
            "DATABASE_URL",
            default="postgres://sentinex:sentinex@localhost:5432/sentinex",
        ),
        "ENGINE": "django_tenants.postgresql_backend",
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# ---------------------------------------------------------------------------
# Redis / Cache / Celery
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/Prague"

# Periodic tasks. ``data_access.knowledge_incremental_dispatch`` and
# ``data_access.workspace_directory_dispatch`` fan out per active tenant.
CELERY_BEAT_SCHEDULE: dict[str, dict[str, object]] = {
    "knowledge-incremental-every-5min": {
        "task": "data_access.knowledge_incremental_dispatch",
        "schedule": 300.0,
    },
    "workspace-directory-daily": {
        "task": "data_access.workspace_directory_dispatch",
        "schedule": 86400.0,
    },
    "workspace-audit-hourly": {
        "task": "data_access.workspace_audit_dispatch",
        "schedule": 3600.0,
    },
    "slack-sync-every-6h": {
        "task": "data_access.sync_slack_dispatch",
        "schedule": 21600.0,
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# i18n, tz, static
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "cs"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------
TENANT_HOST = env("TENANT_HOST", default="sentinex.local")
PUBLIC_SCHEMA_NAME = "public"

# ---------------------------------------------------------------------------
# LLM / External
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Domain-Wide Delegation (Service Account) — single connector for entire Workspace.
# Path to service-account.json on disk OR raw JSON in env var.
GOOGLE_WORKSPACE_SA_JSON_PATH = env("GOOGLE_WORKSPACE_SA_JSON_PATH", default="")
GOOGLE_WORKSPACE_SA_JSON = env("GOOGLE_WORKSPACE_SA_JSON", default="")
GOOGLE_WORKSPACE_DOMAIN = env("GOOGLE_WORKSPACE_DOMAIN", default="")
GOOGLE_WORKSPACE_ADMIN_EMAIL = env("GOOGLE_WORKSPACE_ADMIN_EMAIL", default="")

# Full read-only scope set for company-wide ingestion.
GOOGLE_WORKSPACE_DWD_SCOPES = [
    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",
    # Drive
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    # Calendar
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    # Docs / Sheets / Slides
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    # People / Contacts / Directory
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
    # Admin SDK Directory (admin-only)
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
    # Admin SDK Reports (audit + usage)
    "https://www.googleapis.com/auth/admin.reports.audit.readonly",
    "https://www.googleapis.com/auth/admin.reports.usage.readonly",
    # Tasks / Keep
    "https://www.googleapis.com/auth/tasks.readonly",
    "https://www.googleapis.com/auth/keep.readonly",
    # Chat (Workspace only)
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
]

# Knowledge ingestion configuration
KNOWLEDGE_EMBEDDING_MODEL = env("KNOWLEDGE_EMBEDDING_MODEL", default="text-embedding-3-small")
KNOWLEDGE_EMBEDDING_DIMENSIONS = env.int("KNOWLEDGE_EMBEDDING_DIMENSIONS", default=1536)
KNOWLEDGE_CHUNK_SIZE_TOKENS = env.int("KNOWLEDGE_CHUNK_SIZE_TOKENS", default=800)
KNOWLEDGE_CHUNK_OVERLAP_TOKENS = env.int("KNOWLEDGE_CHUNK_OVERLAP_TOKENS", default=100)
KNOWLEDGE_MAX_FILE_BYTES = env.int("KNOWLEDGE_MAX_FILE_BYTES", default=20_000_000)  # 20 MB
KNOWLEDGE_STUB_MODE = env.bool("KNOWLEDGE_STUB_MODE", default=False)

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
LLM_DEFAULT_MODEL = env("LLM_DEFAULT_MODEL", default="claude-sonnet-4-20250514")
LLM_FALLBACK_MODEL = env("LLM_FALLBACK_MODEL", default="claude-haiku-4-5-20251001")
LLM_CACHE_ENABLED = env("LLM_CACHE_ENABLED")
LLM_CACHE_DEFAULT_TTL = env("LLM_CACHE_DEFAULT_TTL")
USD_TO_CZK = env("USD_TO_CZK")

CRYPTOGRAPHY_KEY = env("CRYPTOGRAPHY_KEY", default="insecure-dev-cryptography-key-change")

# ---------------------------------------------------------------------------
# Sentry (initialized only when SENTRY_DSN is set; SDK optional in dev)
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development")

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        def _before_send(event: dict, hint: dict) -> dict:
            try:
                from django.db import connection

                tenant = connection.get_tenant() if hasattr(connection, "get_tenant") else None
                if tenant is not None:
                    event.setdefault("tags", {})["tenant"] = getattr(
                        tenant, "schema_name", str(tenant)
                    )
            except Exception:
                pass
            return event

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            before_send=_before_send,
            send_default_pii=False,
        )
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE = env("SESSION_COOKIE_AGE")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@sentinex.local")

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
    },
}
