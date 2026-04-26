"""Core shared-schema models: Tenant, Domain, User, TenantMembership, Invitation."""

from __future__ import annotations

import secrets
from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name: models.CharField[str, str] = models.CharField(max_length=100)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    is_active: models.BooleanField[bool, bool] = models.BooleanField(default=True)

    auto_create_schema = True
    auto_drop_schema = False

    def __str__(self) -> str:
        return str(self.name)


class Domain(DomainMixin):
    pass


class UserManager(BaseUserManager["User"]):
    """Email-based user manager."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra.get("is_staff") or not extra.get("is_superuser"):
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Email-as-username user."""

    username = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return str(self.email)


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class TenantMembership(models.Model):
    """Links a User to a Tenant with a role. Shared schema."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "tenant")
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["user", "tenant"])]

    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant} ({self.role})"


def _new_token() -> str:
    return secrets.token_urlsafe(32)


class Invitation(models.Model):
    """Invitation to join a tenant. Shared schema."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=_new_token)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations_sent"
    )
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    accepted_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["email", "tenant"])]

    def __str__(self) -> str:
        return f"Invite {self.email} -> {self.tenant} ({self.role})"

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    def accept(self, user: User) -> TenantMembership:
        membership, _ = TenantMembership.objects.get_or_create(
            user=user, tenant=self.tenant, defaults={"role": self.role}
        )
        self.accepted_at = timezone.now()  # type: ignore[assignment]
        self.save(update_fields=["accepted_at"])
        return membership


class AddonActivation(models.Model):
    """Per-tenant addon activation record. Shared schema."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="addon_activations")
    addon_name = models.CharField(max_length=64, db_index=True)
    active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)
    activated_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)
    deactivated_at: models.DateTimeField[None, None] = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("tenant", "addon_name")
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["tenant", "addon_name"])]

    def __str__(self) -> str:
        return f"{self.addon_name}@{self.tenant} {'on' if self.active else 'off'}"


class TenantBudget(models.Model):
    """Per-tenant monthly spend cap. Shared schema for cross-tenant billing views."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="budget")
    monthly_limit_czk = models.DecimalField(max_digits=12, decimal_places=2, default=1000)
    per_conversation_limit_czk = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    current_month_spent_czk = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    period_start = models.DateField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Budget({self.tenant}): {self.current_month_spent_czk}/{self.monthly_limit_czk}"


class ComplianceLog(models.Model):
    """EU AI Act compliance record. One row per agent invocation."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_logs"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_logs"
    )
    agent = models.CharField(max_length=64)
    model = models.CharField(max_length=64)
    prompt_hash = models.CharField(max_length=64)
    response_hash = models.CharField(max_length=64, blank=True)
    success = models.BooleanField(default=True)
    error = models.CharField(max_length=200, blank=True)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.agent}/{self.model} ok={self.success} @ {self.created_at:%Y-%m-%d}"


class LLMUsage(models.Model):
    """Shared-schema audit log for every LLM call.

    ``tenant`` is nullable for system-level calls (e.g. admin probes).
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="llm_usage"
    )
    model = models.CharField(max_length=64)
    prompt_hash = models.CharField(max_length=64, db_index=True)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_czk = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    cached = models.BooleanField(default=False)
    latency_ms = models.IntegerField(default=0)
    created_at: models.DateTimeField[None, None] = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["model", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.model} @ {self.tenant_id or '-'} ({self.input_tokens}/{self.output_tokens})"
