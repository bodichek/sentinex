"""Auth + membership + invitation flow tests."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import Domain, Invitation, Role, Tenant, TenantMembership, User


@pytest.mark.django_db(transaction=True)
class TestSignup:
    def test_signup_creates_user(self, client: Client) -> None:
        resp = client.post(
            reverse("account_signup"),
            {
                "email": "new@example.com",
                "password1": "s3cret-password!",
                "password2": "s3cret-password!",
            },
        )
        assert resp.status_code in (200, 302)
        assert User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db(transaction=True)
class TestLogin:
    def test_login_with_valid_credentials(self, client: Client) -> None:
        User.objects.create_user(email="u@example.com", password="pw-xyz-1234")
        resp = client.post(
            reverse("account_login"),
            {"login": "u@example.com", "password": "pw-xyz-1234"},
        )
        assert resp.status_code in (200, 302)


@pytest.mark.django_db(transaction=True)
class TestMembershipEnforcement:
    def test_invitation_accept_creates_membership(self) -> None:
        tenant = Tenant.objects.create(schema_name="inv_t", name="Inv T")
        Domain.objects.create(domain="inv.sentinex.local", tenant=tenant, is_primary=True)
        invitation = Invitation.objects.create(
            tenant=tenant, email="invitee@example.com", role=Role.ADMIN
        )
        user = User.objects.create_user(email="invitee@example.com", password="pw-12345678")

        invitation.accept(user)

        invitation.refresh_from_db()
        assert invitation.is_accepted
        membership = TenantMembership.objects.get(user=user, tenant=tenant)
        assert membership.role == Role.ADMIN

    def test_no_membership_view_accessible(self, client: Client) -> None:
        resp = client.get(reverse("no_membership"))
        assert resp.status_code == 403

    def test_dashboard_requires_login(self, client: Client) -> None:
        resp = client.get(reverse("dashboard"))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]
