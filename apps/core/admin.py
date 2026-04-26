"""Django admin registration for shared-schema core models."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.core.models import (
    AddonActivation,
    ComplianceLog,
    Domain,
    Invitation,
    LLMUsage,
    Tenant,
    TenantBudget,
    TenantMembership,
    User,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("schema_name", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("schema_name", "name")
    readonly_fields = ("created_at",)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)
    autocomplete_fields = ("tenant",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):  # type: ignore[type-arg]
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "tenant", "role", "created_at")
    list_filter = ("role", "tenant")
    search_fields = ("user__email", "tenant__name")
    autocomplete_fields = ("user", "tenant")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("email", "tenant", "role", "accepted_at", "created_at")
    list_filter = ("role", "tenant", "accepted_at")
    search_fields = ("email",)
    readonly_fields = ("token", "created_at", "accepted_at")
    autocomplete_fields = ("tenant", "invited_by")


@admin.register(AddonActivation)
class AddonActivationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("addon_name", "tenant", "active", "activated_at")
    list_filter = ("addon_name", "active")
    search_fields = ("addon_name", "tenant__schema_name")


@admin.register(TenantBudget)
class TenantBudgetAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("tenant", "monthly_limit_czk", "current_month_spent_czk", "period_start")


@admin.register(ComplianceLog)
class ComplianceLogAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_at", "tenant", "agent", "model", "success")
    list_filter = ("agent", "model", "success")
    readonly_fields = tuple(f.name for f in ComplianceLog._meta.fields)


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "created_at",
        "tenant",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_czk",
        "cached",
        "latency_ms",
    )
    list_filter = ("model", "tenant", "cached")
    search_fields = ("prompt_hash",)
    readonly_fields = tuple(f.name for f in LLMUsage._meta.fields)
    date_hierarchy = "created_at"

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False
