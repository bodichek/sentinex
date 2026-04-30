"""One-shot dev bootstrap: public tenant + acme tenant + admin user + membership.

Run with:
    poetry run python manage.py shell < scripts/bootstrap_dev.py
"""

from apps.core.models import Domain, Role, Tenant, TenantMembership, User

# 1. Public tenant (shared schema) + localhost domain
public, _ = Tenant.objects.get_or_create(
    schema_name="public", defaults={"name": "Public"}
)
Domain.objects.get_or_create(
    domain="localhost", defaults={"tenant": public, "is_primary": True}
)
Domain.objects.get_or_create(
    domain="127.0.0.1", defaults={"tenant": public, "is_primary": False}
)

# 2. Demo tenant
acme, created = Tenant.objects.get_or_create(
    schema_name="acme", defaults={"name": "Acme"}
)
Domain.objects.get_or_create(
    domain="acme.localhost", defaults={"tenant": acme, "is_primary": True}
)

# 3. Admin user (email = admin@sentinex.local, password = admin)
admin, user_created = User.objects.get_or_create(
    email="admin@sentinex.local",
    defaults={"is_staff": True, "is_superuser": True},
)
if user_created:
    admin.set_password("admin")
    admin.save()

# 4. Owner membership in acme
TenantMembership.objects.get_or_create(
    user=admin, tenant=acme, defaults={"role": Role.OWNER}
)

print("OK")
print(f"  public tenant : id={public.id}")
print(f"  acme tenant   : id={acme.id} (schema acme)")
print(f"  admin user    : {admin.email} / admin")
print(f"  open URL      : http://acme.localhost:8000/integrations/")
