"""List or create Kafka topics for tenants."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.events.topic_manager import ensure_topics, list_topics


class Command(BaseCommand):
    help = "Manage Sentinex Kafka topics."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--create", action="store_true")
        parser.add_argument("--tenant", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        if options["list"]:
            for t in list_topics():
                self.stdout.write(t)
            return
        if options["create"]:
            tenant = options["tenant"]
            if not tenant:
                raise CommandError("--create requires --tenant=<id>")
            created = ensure_topics(tenant)
            for t in created:
                self.stdout.write(self.style.SUCCESS(f"ensured: {t}"))
            return
        raise CommandError("specify --list or --create")
