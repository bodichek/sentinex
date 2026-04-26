# Prompt 03: Authentication Basic

## Goal

Set up user authentication with Django allauth: registration, login, logout, password reset. Define roles (Owner, Admin, Member, Viewer) per tenant.

## Prerequisites

- Prompts 01 and 02 complete
- Tenant and Domain models exist

## Context

Authentication is handled via Django allauth for standard flows. Each user is associated with one or more tenants via role assignments. Users in public schema; role associations in per-tenant schema or as shared TenantUser model — decide based on simplicity.

For MVP: user is a shared model, membership in tenant is also shared. Role is per tenant, per user.

## Constraints

- Use `django-allauth` for auth flows
- Email as username (no separate username field)
- Password hashing: Argon2 (default in Django 5)
- Email verification required for production (optional in dev)
- MFA deferred to post-MVP

## Deliverables

1. `django-allauth` added to dependencies
2. Custom User model in `apps/auth/` (or use Django default with email as USERNAME_FIELD)
3. `TenantMembership` model linking User to Tenant with role
4. Role choices: OWNER, ADMIN, MEMBER, VIEWER
5. Login, signup, logout, password reset URLs wired
6. Templates (minimal Tailwind styling):
   - `templates/account/login.html`
   - `templates/account/signup.html`
   - `templates/account/password_reset.html`
   - `templates/account/password_reset_done.html`
   - `templates/account/password_reset_from_key.html`
7. Settings updated:
   - `AUTH_USER_MODEL`
   - `ACCOUNT_AUTHENTICATION_METHOD = "email"`
   - `ACCOUNT_EMAIL_REQUIRED = True`
   - `ACCOUNT_USERNAME_REQUIRED = False`
   - `ACCOUNT_EMAIL_VERIFICATION = "optional"` (for dev)
   - `LOGIN_REDIRECT_URL = "/dashboard/"`
8. Middleware ensures authenticated user has tenant membership
9. Invitation flow:
   - Tenant admin creates invitation with email and role
   - System sends invitation email (for MVP: print to console)
   - Recipient clicks link, signs up, gets added to tenant with role
10. Basic dashboard view at `/dashboard/` showing logged-in user and tenant info
11. Tests:
    - Signup flow creates user
    - Login works
    - Cannot access tenant without membership
    - Invitation flow creates correct membership

## Acceptance Criteria

- User can register at `/accounts/signup/`
- User receives email verification (dev: prints to console)
- User can log in at `/accounts/login/`
- User can log out at `/accounts/logout/`
- User can reset password
- Tenant owner can invite user via admin or UI
- Invited user signs up and is linked to tenant
- Dashboard shows correct user and tenant
- Tests pass

## Next Steps

After this prompt, proceed to `04-llm-gateway.md`.

## Notes for Claude Code

- Keep UI minimal — functional > polished
- For dev, use console email backend: `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`
- Store role as CharField with choices, easy to extend later
- `TenantMembership` is a shared model (in public schema) — links User to Tenant
- Middleware order: tenancy middleware first, then auth middleware, then membership check
- Add `@require_membership` decorator or mixin for views that need tenant access
- Use `request.tenant_membership.role` to check role in views
