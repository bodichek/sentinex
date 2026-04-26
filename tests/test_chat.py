"""Chat interface tests: create conversation, send message, tenant isolation."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from apps.agents.orchestrator import Intent, OrchestratorResponse
from apps.chat.models import Conversation, Message
from apps.core.models import AddonActivation, Domain, Role, Tenant, TenantMembership, User


def _setup_tenant(schema: str = "test_tenant", host: str = "test.sentinex.local") -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(schema_name=schema, defaults={"name": schema})
    Domain.objects.get_or_create(
        domain=host, defaults={"tenant": tenant, "is_primary": True}
    )
    return tenant


@pytest.fixture
def client_user() -> tuple[Client, Tenant, User]:
    tenant = _setup_tenant()
    user = User.objects.create_user(
        email=f"chat-{uuid.uuid4().hex[:8]}@example.com", password="pw-12345678"
    )
    TenantMembership.objects.create(user=user, tenant=tenant, role=Role.OWNER)
    AddonActivation.objects.update_or_create(
        tenant=tenant, addon_name="weekly_brief", defaults={"active": True}
    )
    client = Client(HTTP_HOST="test.sentinex.local")
    client.force_login(user)
    return client, tenant, user


@pytest.mark.django_db(transaction=True)
class TestChat:
    def test_create_conversation(self, client_user: tuple[Client, Tenant, User]) -> None:
        client, _, _ = client_user
        resp = client.post("/chat/new/")
        assert resp.status_code == 302
        assert resp["Location"].startswith("/chat/")
        # Trailing UUID + slash.
        with schema_context("test_tenant"):
            assert Conversation.objects.count() == 1

    def test_send_message(self, client_user: tuple[Client, Tenant, User]) -> None:
        client, _, user = client_user
        with schema_context("test_tenant"):
            conv = Conversation.objects.create(user_id=user.pk, title="Nový chat")

        fake = OrchestratorResponse(
            intent=Intent(intent="x", summary="x", required_specialists=[]),
            specialist_responses=[],
            final="**Odpověď** od agenta",
        )
        with patch("apps.chat.views.orchestrator.handle", return_value=fake):
            resp = client.post(
                f"/chat/{conv.id}/messages/",
                {"content": "Jak je na tom cashflow?"},
            )

        assert resp.status_code == 302
        with schema_context("test_tenant"):
            msgs = list(Message.objects.filter(conversation=conv).order_by("created_at"))
            assert len(msgs) == 2
            assert msgs[0].role == "user"
            assert msgs[1].role == "assistant"
            assert "agenta" in msgs[1].content
            conv.refresh_from_db()
            assert conv.title.startswith("Jak je na tom")

    def test_conversation_tenant_isolation(
        self, client_user: tuple[Client, Tenant, User]
    ) -> None:
        client, _, user = client_user

        # Create a conversation in a *different* tenant schema (must run in public).
        with schema_context("public"):
            other, _ = Tenant.objects.get_or_create(
                schema_name="other_tenant", defaults={"name": "Other"}
            )
            Domain.objects.get_or_create(
                domain="other.sentinex.local",
                defaults={"tenant": other, "is_primary": True},
            )
        from django.core.management import call_command

        call_command("migrate_schemas", schema_name="other_tenant", verbosity=0)
        with schema_context("other_tenant"):
            foreign = Conversation.objects.create(user_id=user.pk, title="cross")

        # Same UUID does not exist in test_tenant → 404.
        resp = client.get(f"/chat/{foreign.id}/")
        assert resp.status_code == 404
