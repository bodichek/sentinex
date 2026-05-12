"""Tests for :mod:`apps.memory.neo4j_client`."""

from __future__ import annotations

from apps.memory.neo4j_client import TenantNeo4jClient


def test_database_name_prefix_mode_returns_default() -> None:
    client = TenantNeo4jClient(isolation="prefix")
    assert client.get_database_name("tenant-a") == "neo4j"


def test_database_name_database_mode_sanitises_id() -> None:
    client = TenantNeo4jClient(isolation="database")
    assert client.get_database_name("Tenant-A_42") == "tenanttenanta42"


def test_database_name_falls_back_when_id_only_special_chars() -> None:
    client = TenantNeo4jClient(isolation="database")
    assert client.get_database_name("---") == "tenantdefault"
