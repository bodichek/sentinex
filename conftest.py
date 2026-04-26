"""Shared pytest fixtures for django-tenants-aware test DB."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def _ensure_testserver_domain(request: pytest.FixtureRequest) -> None:
    """Guarantee the 'testserver' Domain exists for every test.

    ``TransactionTestCase`` / ``transaction=True`` truncates tables between
    tests; without this, session-scoped setup data would disappear.
    """
    marker = request.node.get_closest_marker("django_db")
    if marker is None:
        return

    if marker.kwargs.get("transaction"):
        request.getfixturevalue("transactional_db")
    else:
        request.getfixturevalue("db")

    from apps.core.models import Domain, Tenant

    tenant, _ = Tenant.objects.get_or_create(
        schema_name="public", defaults={"name": "Public"}
    )
    Domain.objects.get_or_create(
        domain="testserver", defaults={"tenant": tenant, "is_primary": True}
    )


@pytest.fixture(scope="session")
def django_db_setup(
    request: pytest.FixtureRequest,
    django_test_environment: None,
    django_db_blocker: pytest.FixtureRequest,
) -> Iterator[None]:
    """Create the test DB and apply django-tenants migrations.

    pytest-django's default runs Django's ``migrate`` which doesn't handle
    tenant schemas correctly. We manage the test DB lifecycle manually.
    """
    from django.core.management import call_command
    from django.db import connection

    default = settings.DATABASES["default"]
    original_name = default["NAME"]
    test_name = "test_" + original_name
    default["NAME"] = test_name

    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        connection.close()
        with connection._nodb_cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{test_name}"')
            cur.execute(f'CREATE DATABASE "{test_name}"')
        call_command("migrate_schemas", "--shared", verbosity=0)
        from apps.core.models import Domain, Tenant

        tenant, _ = Tenant.objects.get_or_create(
            schema_name="public", defaults={"name": "Public"}
        )
        Domain.objects.get_or_create(
            domain="testserver", defaults={"tenant": tenant, "is_primary": True}
        )
        # Create an always-available "test" tenant and apply tenant migrations.
        test_tenant, _ = Tenant.objects.get_or_create(
            schema_name="test_tenant", defaults={"name": "Test"}
        )
        Domain.objects.get_or_create(
            domain="test.sentinex.local",
            defaults={"tenant": test_tenant, "is_primary": True},
        )
        call_command("migrate_schemas", schema_name="test_tenant", verbosity=0)

    yield

    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        connection.close()
        with connection._nodb_cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{test_name}"')
    default["NAME"] = original_name
