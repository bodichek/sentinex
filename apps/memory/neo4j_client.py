"""Tenant-aware Neo4j client.

Two isolation modes are supported:

* ``prefix`` (Community edition / dev) — single ``neo4j`` database, tenant id
  is stored on every node/edge property and queries filter on it.
* ``database`` (Enterprise / production) — each tenant gets a dedicated
  Neo4j database named ``tenant_<tenant_id>``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from neo4j import AsyncDriver

_TENANT_ID_SAFE = re.compile(r"[^a-zA-Z0-9]")


class TenantNeo4jClient:
    """Resolve Neo4j drivers and database names per tenant."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        isolation: str | None = None,
    ) -> None:
        self.uri: str = uri or str(getattr(settings, "NEO4J_URI", "bolt://localhost:7687"))
        self.user: str = user or str(getattr(settings, "NEO4J_USER", "neo4j"))
        self.password: str = password or str(getattr(settings, "NEO4J_PASSWORD", ""))
        self.isolation = isolation or getattr(
            settings, "NEO4J_TENANT_ISOLATION", "prefix"
        )
        self._driver: AsyncDriver | None = None

    def get_database_name(self, tenant_id: str) -> str:
        """Return the Neo4j database name for a tenant."""
        if self.isolation == "database":
            safe = _TENANT_ID_SAFE.sub("", tenant_id).lower() or "default"
            return f"tenant{safe}"
        return "neo4j"

    async def get_driver(self, tenant_id: str | None = None) -> AsyncDriver:
        """Return a shared async driver. Tenant routing is handled per-session."""
        from neo4j import AsyncGraphDatabase

        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
