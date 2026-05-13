"""Thin wrappers connectors call before persisting Person/Organization rows.

Keeps the existing IdentityResolver service the single source of truth for
matching logic — connectors only build PersonRecord / OrganizationRecord and
let the resolver decide.
"""

from __future__ import annotations

from apps.identity.models import Organization, Person
from apps.identity.services import (
    OrganizationRecord,
    PersonRecord,
    resolver,
)


def resolve_person(
    *,
    source_system: str,
    email: str | None = None,
    full_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    organization: Organization | None = None,
    organization_name: str | None = None,
    person_id_in_source: str | None = None,
    phone: str | None = None,
    slack_id: str | None = None,
    extra_identities: dict[str, str] | None = None,
) -> Person | None:
    """Resolve or create a Person from connector data. Returns None when no
    minimum signal is provided (e.g. no email and no name)."""
    if not any([email, full_name, first_name, last_name, slack_id, person_id_in_source]):
        return None
    record = PersonRecord(
        source_system=source_system,
        email=email,
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        organization_name=organization_name,
        person_id_in_source=person_id_in_source,
        phone=phone,
        slack_id=slack_id,
        extra_identities=extra_identities,
    )
    return resolver.resolve_person(record, organization=organization).person


def resolve_organization(
    *,
    source_system: str,
    name: str,
    ico: str | None = None,
    dic: str | None = None,
    primary_domain: str | None = None,
    id_in_source: str | None = None,
    extra_identities: dict[str, str] | None = None,
) -> Organization | None:
    if not name:
        return None
    record = OrganizationRecord(
        source_system=source_system,
        name=name,
        ico=ico,
        dic=dic,
        primary_domain=primary_domain,
        id_in_source=id_in_source,
        extra_identities=extra_identities,
    )
    return resolver.resolve_organization(record).organization
