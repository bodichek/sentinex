"""Kafka topic management — naming convention and tenant provisioning."""

from __future__ import annotations

import contextlib
import logging
import re
from typing import TYPE_CHECKING

from django.conf import settings

from apps.events.schemas import EventCategory

if TYPE_CHECKING:  # pragma: no cover
    from kafka.admin import KafkaAdminClient

logger = logging.getLogger("sentinex.events")

_TENANT_SAFE = re.compile(r"[^a-zA-Z0-9_-]")

DEFAULT_CATEGORIES: tuple[str, ...] = (
    EventCategory.AGENT.value,
    EventCategory.SYSTEM.value,
    EventCategory.USER.value,
)


def sanitize_tenant_id(tenant_id: str) -> str:
    safe = _TENANT_SAFE.sub("_", tenant_id)
    return safe or "default"


def topic_for(tenant_id: str, category: str) -> str:
    """Return the Kafka topic for a tenant + category."""
    return f"{sanitize_tenant_id(tenant_id)}.events.{category}"


def topics_for_tenant(tenant_id: str) -> list[str]:
    return [topic_for(tenant_id, c) for c in DEFAULT_CATEGORIES]


def _admin_client() -> KafkaAdminClient:
    from kafka.admin import KafkaAdminClient

    return KafkaAdminClient(
        bootstrap_servers=getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        security_protocol=getattr(settings, "KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        client_id="sentinex-admin",
    )


def ensure_topics(
    tenant_id: str,
    *,
    num_partitions: int = 3,
    replication_factor: int = 1,
    retention_ms: int | None = None,
) -> list[str]:
    """Create all per-tenant topics if they don't already exist."""
    from kafka.admin import NewTopic
    from kafka.errors import TopicAlreadyExistsError

    retention = retention_ms or int(
        getattr(settings, "KAFKA_DEFAULT_RETENTION_MS", 7 * 24 * 60 * 60 * 1000)
    )
    desired = topics_for_tenant(tenant_id)
    new_topics = [
        NewTopic(
            name=name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            topic_configs={"retention.ms": str(retention)},
        )
        for name in desired
    ]

    admin = _admin_client()
    try:
        with contextlib.suppress(TopicAlreadyExistsError):
            admin.create_topics(new_topics=new_topics, validate_only=False)
    finally:
        admin.close()
    return desired


def list_topics() -> list[str]:
    admin = _admin_client()
    try:
        return sorted(admin.list_topics())
    finally:
        admin.close()
