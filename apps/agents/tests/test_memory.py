"""Memory tier tests."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django_tenants.utils import schema_context

from apps.agents.memory import LongTermMemory, MediumTermMemory, MemoryManager, ShortTermMemory
from apps.agents.models import Conversation
from apps.core.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
class TestShortTermMemory:
    def test_append_and_read(self) -> None:
        cache.clear()
        mem = ShortTermMemory("c1")
        mem.append("user", "hello")
        mem.append("assistant", "hi")
        turns = mem.read()
        assert [t.role for t in turns] == ["user", "assistant"]

    def test_trims_to_max_turns(self) -> None:
        cache.clear()
        mem = ShortTermMemory("c2", max_turns=3)
        for i in range(5):
            mem.append("user", f"m{i}")
        turns = mem.read()
        assert len(turns) == 3
        assert turns[-1].content == "m4"


@pytest.mark.django_db(transaction=True)
class TestMediumTermMemory:
    def _tenant_with_schema(self, name: str) -> Tenant:
        t: Tenant = Tenant.objects.create(schema_name=name, name=name.upper())
        Domain.objects.create(domain=f"{name}.sentinex.local", tenant=t, is_primary=True)
        return t

    def test_isolation_between_tenants(self) -> None:
        t_a = self._tenant_with_schema("mem_a")
        t_b = self._tenant_with_schema("mem_b")

        with schema_context(t_a.schema_name):
            conv_a = Conversation.objects.create(title="A")
            MediumTermMemory(conv_a).append_message("user", "private-a")

        with schema_context(t_b.schema_name):
            conv_b = Conversation.objects.create(title="B")
            MediumTermMemory(conv_b).append_message("user", "private-b")
            # Tenant B cannot see A's conversation
            assert not Conversation.objects.filter(title="A").exists()


@pytest.mark.django_db(transaction=True)
class TestMemoryManager:
    def test_record_turn_writes_both_tiers(self) -> None:
        cache.clear()
        with schema_context("test_tenant"):
            conv = Conversation.objects.create(title="mgr")
            mgr = MemoryManager(conv)
            mgr.record_turn("user", "hello")
            assert mgr.medium.recent_messages()[0].content == "hello"
        assert mgr.short.read()[0].content == "hello"


@pytest.mark.django_db
class TestLongTermMemory:
    def test_index_swallows_embedding_failures(self) -> None:
        # Without OPENAI_API_KEY (test env), embedding fails — index() returns None.
        assert LongTermMemory().index("hi") is None

    def test_search_returns_empty_on_failure(self) -> None:
        assert LongTermMemory().search("q") == []
