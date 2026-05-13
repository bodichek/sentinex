"""Test settings."""

from config.settings.base import *

DEBUG = False
SECRET_KEY = "test-secret-key"
CRYPTOGRAPHY_KEY = "test-cryptography-key-must-be-32-chars-or-more"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
