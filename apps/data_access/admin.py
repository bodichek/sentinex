"""Admin for data_access (tenant-scoped models)."""

from __future__ import annotations

from typing import Any

from django.contrib import admin

from apps.data_access.models import (
    Credential,
    DataSnapshot,
    IngestionCursor,
    Integration,
    ManualKPI,
    MCPCall,
    WorkspaceDocument,
)


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("provider", "is_active", "connected_at", "last_sync_at")
    list_filter = ("provider", "is_active")


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("integration", "created_at", "updated_at")
    readonly_fields = ("integration", "created_at", "updated_at")

    def has_add_permission(self, request: Any) -> bool:
        return False

    def get_fields(self, request: Any, obj: Any = None) -> Any:
        return ["integration", "created_at", "updated_at"]


@admin.register(MCPCall)
class MCPCallAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_at", "integration", "tool", "ok", "latency_ms")
    list_filter = ("tool", "ok")
    search_fields = ("params_hash",)
    readonly_fields = tuple(f.name for f in MCPCall._meta.fields)

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False


@admin.register(DataSnapshot)
class DataSnapshotAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("source", "period_start", "period_end", "created_at")
    list_filter = ("source",)
    readonly_fields = ("created_at",)


@admin.register(ManualKPI)
class ManualKPIAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "value", "unit", "period_end", "created_at")
    list_filter = ("name", "unit")
    search_fields = ("name", "notes")


@admin.register(WorkspaceDocument)
class WorkspaceDocumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "source",
        "mime_type",
        "owner_email",
        "status",
        "modified_at",
        "indexed_at",
    )
    list_filter = ("source", "status", "mime_type")
    search_fields = ("title", "external_id", "owner_email")
    readonly_fields = (
        "source",
        "external_id",
        "size_bytes",
        "text_truncated",
        "extracted_at",
        "indexed_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "modified_at"


@admin.register(IngestionCursor)
class IngestionCursorAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "source",
        "cursor",
        "last_full_sync_at",
        "last_incremental_sync_at",
        "files_total",
        "files_indexed",
        "files_failed",
    )
    readonly_fields = ("last_full_sync_at", "last_incremental_sync_at")
