"""Create required Postgres extensions."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import DatabaseError


class Command(BaseCommand):
    help = "Create required Postgres extensions (pgvector, btree_gin)."

    REQUIRED = ("btree_gin",)
    OPTIONAL = ("vector",)

    def handle(self, *args: Any, **options: Any) -> None:
        with connection.cursor() as cursor:
            for ext in self.REQUIRED:
                cursor.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
                self.stdout.write(self.style.SUCCESS(f"extension ready: {ext}"))
            for ext in self.OPTIONAL:
                try:
                    cursor.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
                    self.stdout.write(self.style.SUCCESS(f"extension ready: {ext}"))
                except DatabaseError as exc:
                    self.stdout.write(
                        self.style.WARNING(
                            f"optional extension '{ext}' not installed — skipped ({exc})"
                        )
                    )
