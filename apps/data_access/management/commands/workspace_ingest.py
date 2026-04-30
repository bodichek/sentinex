"""On-demand Workspace ingestion runner.

Examples
--------
    python manage.py workspace_ingest --tenant=acme --mode=full
    python manage.py workspace_ingest --tenant=acme --mode=incremental
    python manage.py workspace_ingest --tenant=acme --mode=directory --domain=acme.com
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Run Workspace ingestion (full / incremental / directory) for a tenant."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True, help="Tenant schema name")
        parser.add_argument(
            "--mode",
            required=True,
            choices=["full", "incremental", "directory", "audit"],
            help="What to run",
        )
        parser.add_argument("--domain", default=None, help="Workspace domain for directory sync")
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args: Any, **opts: Any) -> None:
        tenant = opts["tenant"]
        mode = opts["mode"]

        with schema_context(tenant):
            if mode == "full":
                from apps.data_access.knowledge.tasks import full_ingest_workspace

                result = full_ingest_workspace()
            elif mode == "incremental":
                from apps.data_access.knowledge.tasks import incremental_ingest_workspace

                result = incremental_ingest_workspace()
            elif mode == "directory":
                from apps.data_access.sync.google_workspace_dwd import sync_directory_users

                domain = opts["domain"] or settings.GOOGLE_WORKSPACE_DOMAIN
                if not domain:
                    raise CommandError("--domain or GOOGLE_WORKSPACE_DOMAIN required")
                result = sync_directory_users(domain)
            elif mode == "audit":
                from apps.data_access.sync.google_workspace_dwd import sync_admin_audit_logins

                result = sync_admin_audit_logins(days=opts["days"])
            else:
                raise CommandError(f"unknown mode: {mode}")

        self.stdout.write(self.style.SUCCESS(f"OK {mode}: {result}"))
