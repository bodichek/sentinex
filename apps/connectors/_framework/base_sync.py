"""BaseSync — the contract every connector ingest implements.

A subclass implements ``fetch()`` (yield raw items) and ``persist(item, ctx)``
(map+upsert one item with provenance and identity resolution). BaseSync wraps
this with:

- SyncRun lifecycle (pending → running → completed/partial/failed)
- Per-provider TokenBucket rate limiter (optional)
- Retry on transient errors
- Aggregated counters
- Structured error capture

The subclass owns model knowledge; the framework owns orchestration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.connectors._framework.models import SyncMode, SyncRun, SyncStatus
from apps.connectors._framework.rate_limit import TokenBucket
from apps.data_access.models import IngestionCursor, Integration

logger = logging.getLogger(__name__)


@dataclass
class SyncContext:
    """Per-run context passed to persist() and helpers."""

    run: SyncRun
    integration: Integration
    provider: str
    resource: str
    mode: str
    cursor_before: str = ""
    cursor_after: str = ""

    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_samples: list[str] = field(default_factory=list)

    def record_error(self, err: BaseException) -> None:
        self.errors += 1
        if len(self.error_samples) < 5:
            self.error_samples.append(f"{type(err).__name__}: {err}"[:300])


@dataclass
class SyncOutcome:
    status: str
    fetched: int
    created: int
    updated: int
    skipped: int
    errors: int
    cursor_after: str = ""


class BaseSync(ABC):
    """Subclass once per (provider, resource) pair.

    Example:
        class PipedriveDealSync(BaseSync):
            provider = "pipedrive"
            resource = "deals"
            rate_limit = TokenBucket("pipedrive", capacity=80, refill_per_sec=40)
            def fetch(self, ctx): ...
            def persist(self, raw, ctx): ...
    """

    provider: str = ""
    resource: str = ""
    rate_limit: TokenBucket | None = None
    cursor_source: str = ""  # overrides default cursor key (default: f"{provider}.{resource}")

    def __init__(self, integration: Integration) -> None:
        self.integration = integration
        if not self.provider or not self.resource:
            raise RuntimeError("BaseSync subclass must set provider and resource")

    # ----------------------------------------------------------- subclass API
    @abstractmethod
    def fetch(self, ctx: SyncContext) -> Iterator[Any]:
        """Yield raw items (typically dicts) from the source system."""

    @abstractmethod
    def persist(self, raw: Any, ctx: SyncContext) -> str:
        """Persist one raw item and return one of "created", "updated", "skipped".

        Implementations should:
          1. extract identity fields, call identity_hook.resolve_*
          2. upsert the row with ProvenanceMixin fields populated
          3. attach ctx.run to sync_run FK
        """

    # ------------------------------------------------------------ entry point
    def run(self, *, mode: str = SyncMode.INCREMENTAL) -> SyncOutcome:
        cursor_key = self.cursor_source or f"{self.provider}.{self.resource}"
        cursor_before = self._read_cursor(cursor_key)
        run = SyncRun.objects.create(
            integration=self.integration,
            provider=self.provider,
            resource=self.resource,
            mode=mode,
            status=SyncStatus.PENDING,
            cursor_before=cursor_before,
        )
        ctx = SyncContext(
            run=run,
            integration=self.integration,
            provider=self.provider,
            resource=self.resource,
            mode=mode,
            cursor_before=cursor_before,
        )
        with self._timing(run):
            run.status = SyncStatus.RUNNING
            run.started_at = timezone.now()
            run.save(update_fields=["status", "started_at"])
            try:
                for raw in self.fetch(ctx):
                    if self.rate_limit is not None:
                        self.rate_limit.acquire(1)
                    self._persist_one(raw, ctx)
            except Exception as exc:
                logger.exception("sync %s.%s failed", self.provider, self.resource)
                run.status = SyncStatus.FAILED
                run.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                run.errors_count = ctx.errors + 1
                self._finalize_run(run, ctx)
                return SyncOutcome(SyncStatus.FAILED, ctx.fetched, ctx.created,
                                   ctx.updated, ctx.skipped, ctx.errors + 1, ctx.cursor_after)

            if ctx.errors == 0:
                run.status = SyncStatus.COMPLETED
            else:
                run.status = SyncStatus.PARTIAL
                run.error_message = " | ".join(ctx.error_samples)[:1000]
            self._finalize_run(run, ctx)
            if ctx.cursor_after:
                self._write_cursor(cursor_key, ctx.cursor_after)
        return SyncOutcome(run.status, ctx.fetched, ctx.created, ctx.updated,
                           ctx.skipped, ctx.errors, ctx.cursor_after)

    # ------------------------------------------------------------- internals
    def _persist_one(self, raw: Any, ctx: SyncContext) -> None:
        ctx.fetched += 1
        try:
            with transaction.atomic():
                outcome = self.persist(raw, ctx)
            if outcome == "created":
                ctx.created += 1
            elif outcome == "updated":
                ctx.updated += 1
            elif outcome == "skipped":
                ctx.skipped += 1
        except Exception as exc:
            ctx.record_error(exc)
            logger.warning("sync %s.%s row error: %s", self.provider, self.resource, exc)

    def _finalize_run(self, run: SyncRun, ctx: SyncContext) -> None:
        run.finished_at = timezone.now()
        run.records_fetched = ctx.fetched
        run.records_created = ctx.created
        run.records_updated = ctx.updated
        run.records_skipped = ctx.skipped
        run.errors_count = ctx.errors
        run.cursor_after = ctx.cursor_after
        run.save()

    def _read_cursor(self, source: str) -> str:
        row = IngestionCursor.objects.filter(source=source).first()
        return row.cursor if row else ""

    def _write_cursor(self, source: str, value: str) -> None:
        IngestionCursor.objects.update_or_create(
            source=source,
            defaults={"cursor": value, "last_incremental_sync_at": timezone.now()},
        )

    @contextmanager
    def _timing(self, run: SyncRun) -> Iterator[None]:
        start: datetime = timezone.now()
        try:
            yield
        finally:
            logger.info(
                "sync %s.%s duration=%.2fs status=%s",
                self.provider, self.resource,
                (timezone.now() - start).total_seconds(), run.status,
            )
