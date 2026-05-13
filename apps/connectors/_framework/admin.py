from django.contrib import admin

from apps.connectors._framework.models import SyncRun


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "resource",
        "mode",
        "status",
        "started_at",
        "records_fetched",
        "records_created",
        "records_updated",
        "errors_count",
    )
    list_filter = ("provider", "status", "mode")
    search_fields = ("provider", "resource", "error_message")
    readonly_fields = (
        "id",
        "integration",
        "provider",
        "resource",
        "mode",
        "status",
        "started_at",
        "finished_at",
        "cursor_before",
        "cursor_after",
        "records_fetched",
        "records_created",
        "records_updated",
        "records_skipped",
        "errors_count",
        "error_message",
        "extra",
    )
