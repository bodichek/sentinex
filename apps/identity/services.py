"""Identity resolver — exact + fuzzy matching for Person/Organization.

AI matching and Slack `users.lookupByEmail` enrichment are wired in as hooks
but the heavy lifting lives elsewhere (LLM gateway, Slack connector).
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from django.db import transaction
from django.utils import timezone

from apps.identity.models import (
    IdentityType,
    MatchMethod,
    Organization,
    OrganizationIdentity,
    OrganizationType,
    Person,
    PersonIdentity,
    PersonOrganizationRole,
    PersonRole,
    PersonType,
    SourceSystem,
)


@dataclass(slots=True)
class PersonRecord:
    """Inbound record from a connector before it has been resolved to a Person."""

    source_system: str
    email: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    organization_name: str | None = None
    organization_id_in_source: str | None = None
    person_id_in_source: str | None = None
    phone: str | None = None
    slack_id: str | None = None
    extra_identities: dict[str, str] | None = None  # identity_type → value


@dataclass(slots=True)
class OrganizationRecord:
    source_system: str
    name: str
    ico: str | None = None
    dic: str | None = None
    primary_domain: str | None = None
    id_in_source: str | None = None
    extra_identities: dict[str, str] | None = None


@dataclass(slots=True)
class ResolveResult:
    person: Person | None
    organization: Organization | None
    matched_by: str
    confidence: float
    created_person: bool = False
    created_organization: bool = False


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _identity_type_for_source_person(source: str) -> str:
    mapping = {
        SourceSystem.PIPEDRIVE: IdentityType.PIPEDRIVE_PERSON_ID,
        SourceSystem.FAPI: IdentityType.FAPI_CUSTOMER_ID,
        SourceSystem.BR: IdentityType.BR_USER_ID,
        SourceSystem.SLACK: IdentityType.SLACK_ID,
        SourceSystem.GOOGLE: IdentityType.GOOGLE_ID,
    }
    return mapping.get(source, IdentityType.EMAIL)


def _identity_type_for_source_org(source: str) -> str:
    mapping = {
        SourceSystem.PIPEDRIVE: IdentityType.PIPEDRIVE_ORG_ID,
        SourceSystem.FAPI: IdentityType.FAPI_CUSTOMER_ID,
    }
    return mapping.get(source, IdentityType.DOMAIN)


class IdentityResolver:
    """Find or create a Person/Organization from an inbound connector record.

    Resolution order for Person:
      1. PersonIdentity exact match on any provided identifier (incl. email).
      2. Email domain + fuzzy name match → existing Person at same Organization.
      3. Otherwise create a new Person (and PersonIdentity rows).

    AI-based matching is not invoked here; callers that want it should call
    `find_candidates()` and feed results to the LLM matcher.
    """

    FUZZY_NAME_THRESHOLD = 0.85

    # ------------------------------------------------------------------ Person
    @transaction.atomic
    def resolve_person(
        self, record: PersonRecord, *, organization: Organization | None = None
    ) -> ResolveResult:
        identities = self._collect_person_identities(record)

        # 1. exact identity match
        for itype, ivalue in identities:
            existing = PersonIdentity.objects.select_related("person").filter(
                identity_type=itype, identity_value=ivalue
            ).first()
            if existing:
                self._touch_identity(existing, record.source_system)
                self._merge_person_fields(existing.person, record)
                return ResolveResult(
                    person=existing.person,
                    organization=organization,
                    matched_by=MatchMethod.IDENTITY_EXACT,
                    confidence=1.0,
                )

        # 2. fuzzy: email domain + name within same organization
        if record.email and (record.full_name or (record.first_name and record.last_name)):
            domain = record.email.split("@", 1)[-1].lower() if "@" in record.email else ""
            candidates = Person.objects.filter(primary_email__iendswith=f"@{domain}")
            if organization is not None:
                candidates = candidates.filter(org_roles__organization=organization).distinct()
            target_name = record.full_name or f"{record.first_name} {record.last_name}".strip()
            best: tuple[Person, float] | None = None
            for cand in candidates[:50]:
                score = _similarity(cand.display_name, target_name)
                if score >= self.FUZZY_NAME_THRESHOLD and (best is None or score > best[1]):
                    best = (cand, score)
            if best:
                person, score = best
                self._merge_person_fields(person, record)
                self._upsert_identities(person, identities, record.source_system)
                return ResolveResult(
                    person=person,
                    organization=organization,
                    matched_by=MatchMethod.NAME_DOMAIN_FUZZY,
                    confidence=score,
                )

        # 3. create new Person
        person = Person.objects.create(
            display_name=record.full_name or f"{record.first_name or ''} {record.last_name or ''}".strip() or (record.email or ""),
            first_name=record.first_name or "",
            last_name=record.last_name or "",
            primary_email=record.email or "",
            person_type=PersonType.CONTACT,
            confidence=0.8,
        )
        self._upsert_identities(person, identities, record.source_system)
        if organization is not None:
            PersonOrganizationRole.objects.get_or_create(
                person=person,
                organization=organization,
                role=PersonRole.CONTACT,
                defaults={"source_system": record.source_system},
            )
        return ResolveResult(
            person=person,
            organization=organization,
            matched_by=MatchMethod.MANUAL,
            confidence=0.8,
            created_person=True,
        )

    # ------------------------------------------------------------ Organization
    @transaction.atomic
    def resolve_organization(self, record: OrganizationRecord) -> ResolveResult:
        identities = self._collect_org_identities(record)

        # 1. exact identity match
        for itype, ivalue in identities:
            existing = OrganizationIdentity.objects.select_related("organization").filter(
                identity_type=itype, identity_value=ivalue
            ).first()
            if existing:
                self._touch_org_identity(existing, record.source_system)
                return ResolveResult(
                    person=None,
                    organization=existing.organization,
                    matched_by=MatchMethod.IDENTITY_EXACT,
                    confidence=1.0,
                )

        # 2. fuzzy: name match with normalized comparison
        candidates = Organization.objects.filter(merged_into__isnull=True)[:200]
        target = _norm(record.name)
        best: tuple[Organization, float] | None = None
        for cand in candidates:
            score = _similarity(cand.name, target)
            if score >= self.FUZZY_NAME_THRESHOLD and (best is None or score > best[1]):
                best = (cand, score)
        if best:
            org, score = best
            self._upsert_org_identities(org, identities, record.source_system)
            return ResolveResult(
                person=None,
                organization=org,
                matched_by=MatchMethod.NAME_COMPANY_FUZZY,
                confidence=score,
            )

        # 3. create new Organization
        org = Organization.objects.create(
            name=record.name,
            ico=record.ico or "",
            dic=record.dic or "",
            primary_domain=record.primary_domain or "",
            org_type=OrganizationType.CLIENT,
            confidence=0.8,
        )
        self._upsert_org_identities(org, identities, record.source_system)
        return ResolveResult(
            person=None,
            organization=org,
            matched_by=MatchMethod.MANUAL,
            confidence=0.8,
            created_organization=True,
        )

    # ----------------------------------------------------------------- helpers
    def _collect_person_identities(self, record: PersonRecord) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if record.email:
            out.append((IdentityType.EMAIL, record.email.lower()))
        if record.slack_id:
            out.append((IdentityType.SLACK_ID, record.slack_id))
        if record.phone:
            out.append((IdentityType.PHONE, record.phone))
        if record.person_id_in_source:
            out.append((_identity_type_for_source_person(record.source_system), record.person_id_in_source))
        for itype, ival in (record.extra_identities or {}).items():
            out.append((itype, ival))
        return out

    def _collect_org_identities(self, record: OrganizationRecord) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if record.ico:
            out.append((IdentityType.ICO, record.ico))
        if record.dic:
            out.append((IdentityType.DIC, record.dic))
        if record.primary_domain:
            out.append((IdentityType.DOMAIN, record.primary_domain.lower()))
        if record.id_in_source:
            out.append((_identity_type_for_source_org(record.source_system), record.id_in_source))
        for itype, ival in (record.extra_identities or {}).items():
            out.append((itype, ival))
        return out

    def _upsert_identities(
        self, person: Person, identities: list[tuple[str, str]], source: str
    ) -> None:
        for itype, ivalue in identities:
            PersonIdentity.objects.update_or_create(
                identity_type=itype,
                identity_value=ivalue,
                defaults={
                    "person": person,
                    "source_system": source,
                    "last_seen": timezone.now(),
                },
            )

    def _upsert_org_identities(
        self, org: Organization, identities: list[tuple[str, str]], source: str
    ) -> None:
        for itype, ivalue in identities:
            OrganizationIdentity.objects.update_or_create(
                identity_type=itype,
                identity_value=ivalue,
                defaults={
                    "organization": org,
                    "source_system": source,
                    "last_seen": timezone.now(),
                },
            )

    def _touch_identity(self, identity: PersonIdentity, source: str) -> None:
        identity.last_seen = timezone.now()
        if not identity.verified and source != SourceSystem.AI_MATCH:
            identity.verified = True
        identity.save(update_fields=["last_seen", "verified"])

    def _touch_org_identity(self, identity: OrganizationIdentity, source: str) -> None:
        identity.last_seen = timezone.now()
        if not identity.verified and source != SourceSystem.AI_MATCH:
            identity.verified = True
        identity.save(update_fields=["last_seen", "verified"])

    def _merge_person_fields(self, person: Person, record: PersonRecord) -> None:
        """Fill in empty fields from inbound record; never overwrite verified data."""
        changed: list[str] = []
        if not person.primary_email and record.email:
            person.primary_email = record.email
            changed.append("primary_email")
        if not person.first_name and record.first_name:
            person.first_name = record.first_name
            changed.append("first_name")
        if not person.last_name and record.last_name:
            person.last_name = record.last_name
            changed.append("last_name")
        if not person.display_name and record.full_name:
            person.display_name = record.full_name
            changed.append("display_name")
        if changed:
            person.save(update_fields=changed)


resolver = IdentityResolver()
