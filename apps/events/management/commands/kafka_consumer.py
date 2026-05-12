"""Run a Kafka consumer loop."""

from __future__ import annotations

import asyncio
from typing import Any

from django.core.management.base import BaseCommand

from apps.events.consumers.agent_consumer import dispatch
from apps.events.kafka_client import SentinexKafkaConsumer


class Command(BaseCommand):
    help = "Run the Sentinex Kafka consumer loop for agent events."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", default="all")
        parser.add_argument("--group", default="sentinex-agent")
        parser.add_argument(
            "--categories",
            default="agent",
            help="Comma-separated categories: agent,system,user",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        categories = [c.strip() for c in options["categories"].split(",") if c.strip()]
        tenant = options["tenant"]
        group = options["group"]

        consumer = SentinexKafkaConsumer()
        self.stdout.write(self.style.SUCCESS(f"consuming tenant={tenant} cats={categories}"))
        asyncio.run(consumer.subscribe(tenant, categories, dispatch, group_id=group))
