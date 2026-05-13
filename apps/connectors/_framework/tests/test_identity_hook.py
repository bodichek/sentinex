from __future__ import annotations

import pytest

from apps.connectors._framework.identity_hook import (
    resolve_organization,
    resolve_person,
)
from apps.identity.models import Person, PersonIdentity


@pytest.mark.django_db
def test_resolve_person_returns_none_when_no_signal() -> None:
    assert resolve_person(source_system="pipedrive") is None


@pytest.mark.django_db
def test_resolve_person_creates_new() -> None:
    person = resolve_person(
        source_system="pipedrive",
        email="jan@acme.cz",
        full_name="Jan Novák",
    )
    assert person is not None
    assert Person.objects.filter(id=person.id).exists()
    assert PersonIdentity.objects.filter(person=person, identity_value="jan@acme.cz").exists()


@pytest.mark.django_db
def test_resolve_organization_returns_none_without_name() -> None:
    assert resolve_organization(source_system="fapi", name="") is None


@pytest.mark.django_db
def test_resolve_organization_creates_and_reuses_by_ico() -> None:
    org1 = resolve_organization(
        source_system="fapi", name="ACME s.r.o.", ico="12345678"
    )
    org2 = resolve_organization(
        source_system="pipedrive", name="ACME", ico="12345678"
    )
    assert org1 is not None and org2 is not None
    assert org1.id == org2.id
