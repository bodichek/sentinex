from django.contrib import admin

from apps.identity.models import (
    Organization,
    OrganizationIdentity,
    Person,
    PersonIdentity,
    PersonMergeLog,
    PersonOrganizationRole,
)


class PersonIdentityInline(admin.TabularInline):
    model = PersonIdentity
    extra = 0
    fields = ("identity_type", "identity_value", "source_system", "verified", "confidence")


class PersonOrganizationRoleInline(admin.TabularInline):
    model = PersonOrganizationRole
    extra = 0
    fk_name = "person"
    fields = ("organization", "role", "is_primary", "valid_from", "valid_to", "source_system")


class OrganizationIdentityInline(admin.TabularInline):
    model = OrganizationIdentity
    extra = 0
    fields = ("identity_type", "identity_value", "source_system", "verified", "confidence")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("display_name", "primary_email", "person_type", "confidence", "created_at")
    list_filter = ("person_type",)
    search_fields = ("display_name", "first_name", "last_name", "primary_email")
    inlines = [PersonIdentityInline, PersonOrganizationRoleInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "org_type", "ico", "primary_domain", "tenant", "created_at")
    list_filter = ("org_type",)
    search_fields = ("name", "legal_name", "ico", "dic", "primary_domain")
    inlines = [OrganizationIdentityInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(PersonIdentity)
class PersonIdentityAdmin(admin.ModelAdmin):
    list_display = ("identity_type", "identity_value", "person", "source_system", "verified")
    list_filter = ("identity_type", "source_system", "verified")
    search_fields = ("identity_value",)
    autocomplete_fields = ("person",)


@admin.register(OrganizationIdentity)
class OrganizationIdentityAdmin(admin.ModelAdmin):
    list_display = ("identity_type", "identity_value", "organization", "source_system", "verified")
    list_filter = ("identity_type", "source_system", "verified")
    search_fields = ("identity_value",)
    autocomplete_fields = ("organization",)


@admin.register(PersonOrganizationRole)
class PersonOrganizationRoleAdmin(admin.ModelAdmin):
    list_display = ("person", "organization", "role", "is_primary", "valid_from", "valid_to")
    list_filter = ("role", "is_primary")
    autocomplete_fields = ("person", "organization")


@admin.register(PersonMergeLog)
class PersonMergeLogAdmin(admin.ModelAdmin):
    list_display = ("merged_into", "matched_by", "confidence", "matched_at", "matched_by_user")
    list_filter = ("matched_by",)
    readonly_fields = ("matched_at", "undo_token", "snapshot")
