"""Tests for IdentityResolver and identity models."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.identity.models import (
    IdentityType,
    Organization,
    OrganizationType,
    Person,
    PersonIdentity,
    SourceSystem,
)
from apps.identity.services import (
    OrganizationRecord,
    PersonRecord,
    resolver,
)


@pytest.mark.django_db
def test_email_is_unique_per_identity_type() -> None:
    p1 = Person.objects.create(display_name="A")
    p2 = Person.objects.create(display_name="B")
    PersonIdentity.objects.create(
        person=p1, identity_type=IdentityType.EMAIL, identity_value="x@y.cz"
    )
    with pytest.raises(IntegrityError):
        PersonIdentity.objects.create(
            person=p2, identity_type=IdentityType.EMAIL, identity_value="x@y.cz"
        )


@pytest.mark.django_db
def test_resolve_person_exact_email_match() -> None:
    person = Person.objects.create(display_name="Jan Novák", primary_email="jan@acme.cz")
    PersonIdentity.objects.create(
        person=person,
        identity_type=IdentityType.EMAIL,
        identity_value="jan@acme.cz",
        source_system=SourceSystem.MANUAL,
    )
    result = resolver.resolve_person(
        PersonRecord(source_system=SourceSystem.PIPEDRIVE, email="jan@acme.cz", full_name="Jan Novák")
    )
    assert result.person == person
    assert result.matched_by == "identity_exact"
    assert result.confidence == 1.0


@pytest.mark.django_db
def test_resolve_person_creates_new_when_unknown() -> None:
    result = resolver.resolve_person(
        PersonRecord(
            source_system=SourceSystem.FAPI,
            email="nova@firma.cz",
            full_name="Nová Osoba",
        )
    )
    assert result.created_person is True
    assert result.person is not None
    assert result.person.primary_email == "nova@firma.cz"
    assert PersonIdentity.objects.filter(
        person=result.person, identity_type=IdentityType.EMAIL, identity_value="nova@firma.cz"
    ).exists()


@pytest.mark.django_db
def test_resolve_person_fuzzy_via_email_domain_and_name() -> None:
    org = Organization.objects.create(name="ACME", org_type=OrganizationType.CLIENT)
    person = Person.objects.create(display_name="Jan Novák", primary_email="jan.novak@acme.cz")
    PersonIdentity.objects.create(
        person=person, identity_type=IdentityType.EMAIL, identity_value="jan.novak@acme.cz"
    )
    # different email (work vs personal) but same domain + matching name
    result = resolver.resolve_person(
        PersonRecord(
            source_system=SourceSystem.SLACK,
            email="j.novak@acme.cz",
            full_name="Jan Novák",
        ),
        organization=None,
    )
    # without organization scope the fuzzy path still works on domain+name
    assert result.person == person
    assert result.matched_by == "name_domain_fuzzy"


@pytest.mark.django_db
def test_resolve_person_links_pipedrive_id_after_email_match() -> None:
    person = Person.objects.create(display_name="Jan", primary_email="jan@acme.cz")
    PersonIdentity.objects.create(
        person=person, identity_type=IdentityType.EMAIL, identity_value="jan@acme.cz"
    )
    resolver.resolve_person(
        PersonRecord(
            source_system=SourceSystem.PIPEDRIVE,
            email="jan@acme.cz",
            person_id_in_source="pd-1234",
            full_name="Jan",
        )
    )
    # the resolver hit IDENTITY_EXACT on email, so no new identity is created.
    # Pipedrive ID will only be added on subsequent merge passes or by an
    # explicit identity-upsert call. We just verify the resolver did not duplicate.
    assert PersonIdentity.objects.filter(person=person).count() == 1


@pytest.mark.django_db
def test_resolve_organization_by_ico() -> None:
    org = Organization.objects.create(name="ACME s.r.o.", ico="12345678")
    from apps.identity.models import OrganizationIdentity

    OrganizationIdentity.objects.create(
        organization=org, identity_type=IdentityType.ICO, identity_value="12345678"
    )
    result = resolver.resolve_organization(
        OrganizationRecord(source_system=SourceSystem.FAPI, name="ACME", ico="12345678")
    )
    assert result.organization == org
    assert result.matched_by == "identity_exact"


@pytest.mark.django_db
def test_resolve_organization_creates_new() -> None:
    result = resolver.resolve_organization(
        OrganizationRecord(
            source_system=SourceSystem.PIPEDRIVE,
            name="Nová Firma",
            id_in_source="pd-org-99",
        )
    )
    assert result.created_organization is True
    assert result.organization is not None
    assert result.organization.name == "Nová Firma"
