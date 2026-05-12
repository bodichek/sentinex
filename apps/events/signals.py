"""Provision Kafka topics when a new tenant is created."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Tenant
from apps.events.topic_manager import ensure_topics

logger = logging.getLogger("sentinex.events")


@receiver(post_save, sender=Tenant, dispatch_uid="events_provision_kafka_topics")
def provision_topics_for_tenant(sender: type, instance: Tenant, created: bool, **kwargs: object) -> None:
    if not created:
        return
    try:
        ensure_topics(str(instance.pk))
    except Exception:  # noqa: BLE001
        logger.exception("failed to provision Kafka topics for tenant %s", instance.pk)
