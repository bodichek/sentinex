# Security

Security principles and practices for Sentinex.

## Threat Model

Sentinex is a multi-tenant SaaS platform handling sensitive business data (financial metrics, team signals, strategic decisions). Primary threats:

1. **Cross-tenant data leaks**: tenant A seeing tenant B's data
2. **Credential theft**: attacker stealing OAuth tokens or API keys
3. **Data exfiltration**: leaked data via LLM responses or logs
4. **Unauthorized access**: weak authentication or session hijacking
5. **Supply chain**: compromised dependencies
6. **Insider threats**: malicious or careless operators

## Security Principles

1. **Defense in depth**: multiple layers of protection
2. **Least privilege**: users and services only have what they need
3. **Fail closed**: errors should not expose data
4. **Audit everything**: every access and action is logged
5. **Encrypt sensitive data at rest and in transit**
6. **Minimize data collection**: store only what's necessary

## Authentication

### User Authentication

- Email + password (Django allauth)
- Passwords hashed with Argon2
- MFA planned post-MVP (TOTP or WebAuthn)
- Session timeout: 24 hours inactive
- Account lockout after 5 failed attempts

### API Authentication

- Token-based (Django REST Framework tokens)
- Tokens scoped per user and tenant
- Tokens can be revoked by user
- Rate limiting per token

### OAuth for Integrations

- OAuth 2.0 with PKCE for Google Workspace
- Tokens encrypted at rest (django-cryptography field-level encryption)
- Refresh tokens rotated proactively (5-min buffer before expiry)
- Users can disconnect integrations at any time

## Authorization

### Role-Based Access Control

Per-tenant roles:
- **Owner**: full access, billing control
- **Admin**: full access, no billing
- **Member**: limited features, no sensitive financial data
- **Viewer**: read-only access to approved dashboards

### Permission Enforcement

- Middleware sets `request.user` and `request.tenant`
- Every view checks permissions
- `@permission_required` decorators on view functions
- Permissions also checked in services (defense in depth)

### Decorator: `require_admin`

Defined in `apps/core/middleware.py`. Restricts a view to tenant members
with role **Owner** or **Admin** — anyone else gets HTTP 403. Applied to
destructive or high-cost actions:

- `disconnect(provider)` — toggling an integration off
- `workspace_dwd_ingest` — triggering a full / incremental Workspace
  re-ingest (large embedding spend + Google API quota)

Stack with `@login_required` and `@require_membership` first; `@require_admin`
must run after the membership has been attached to the request.

## Data Isolation

### Tenant Isolation

- Schema per tenant (django-tenants)
- Tenant resolved from subdomain at middleware level
- Database connection switched to tenant schema
- Cross-tenant queries forbidden outside of admin tooling

### Tests for Isolation

Every addon has explicit tenant isolation tests. See [TESTING.md](TESTING.md).

## Encryption

### At Rest

- OAuth tokens: django-cryptography field encryption (Fernet)
- API keys (Anthropic, OpenAI): environment variables, never in database
- Database backups: encrypted at rest on Hetzner storage

### In Transit

- HTTPS everywhere (TLS 1.3)
- HSTS enabled with long max-age
- Certificates via Let's Encrypt (wildcard for subdomains)
- Internal services communicate over private network

### Key Management

MVP: environment variables in `.env` on server.
Production roadmap: migrate to dedicated secrets manager (Doppler, AWS Secrets Manager, HashiCorp Vault).

### `CRYPTOGRAPHY_KEY` hardening

`apps/data_access/models._fernet()` enforces:

- Length **≥ 32 characters**. Shorter keys raise `RuntimeError` at first use.
- Boot **fails** outside `DEBUG` if `CRYPTOGRAPHY_KEY` still equals the
  insecure default `insecure-dev-cryptography-key-change`.
- Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Rotation requires re-encrypting every `Credential.encrypted_tokens` row;
  there is no automatic key-rotation flow yet — see Rotation Playbook below.

## Secrets Management

### Development

- `.env` file (gitignored)
- Copied from `.env.example`
- Never committed to git

### Production

- `.env` on server (permissions 600)
- Secrets rotated every 90 days for high-risk keys (Anthropic, OpenAI)
- SSH key-based server access, no password auth
- Deploy secrets stored in GitHub Actions secrets

### Rotation Playbook

When a secret is compromised:

1. Rotate in source (Anthropic Console, Google Cloud, etc.)
2. Update `.env` on server
3. Restart relevant services
4. Audit logs for suspicious activity
5. Notify affected users if data was accessed

## LLM Security

### Prompt Injection

- Input sanitization before LLM calls
- Pattern matching for known injection attempts
- Separation of system prompts (in YAML, not user input)
- Response validation (format checking)

### Data Leakage

- **PII masking** before LLM calls:
  - Email addresses replaced with `[EMAIL_N]`
  - Phone numbers replaced with `[PHONE_N]`
  - Names replaced with `[NAME_N]`
  - Custom tenant-specific PII patterns
- PII unmasked in responses only for authorized users
- LLM providers are EU-hosted or have DPAs (Anthropic has EU data processing agreement)

### Output Validation

- Responses checked for accidentally leaked data
- Structured outputs validated against schema
- Audit log of all LLM calls (prompt hash, not full prompt)

## Logging and Auditing

### Audit Log

Every significant action logged:
- User login / logout
- Tenant creation / deletion
- Addon activation / deactivation
- LLM calls (metadata, not content)
- Credential updates
- Permission changes
- Data exports

Retention: 36 months (compliance requirement).

### Application Logs

- No PII in logs
- No passwords, tokens, or secrets in logs
- Structured JSON format
- Log level: INFO for normal operations, WARNING/ERROR for issues

### Sentry

- Error stack traces captured
- PII scrubbed before sending to Sentry
- User context limited to user ID (no email, no name)

## GDPR Compliance

### Data Subject Rights

- **Access**: user can export their data (Article 15)
- **Portability**: user can download data in structured format (Article 20)
- **Erasure**: user can delete account and data (Article 17)
- **Rectification**: user can update their data (Article 16)

### Data Processing Agreement

- DPA with Anthropic (LLM processing)
- DPA with OpenAI (embeddings processing)
- DPA with Hetzner (infrastructure)

### Lawful Basis

- Contract: processing necessary for service delivery
- Consent: for marketing communications (opt-in)
- Legitimate interest: for service improvement (with opt-out)

### Data Retention

- User data: deleted 30 days after account deletion
- Audit logs: 36 months
- Tenant data: deleted on tenant deletion (schema drop)
- LLM conversation logs: 12 months

### Notification of Breaches

- Supervisory authority notified within 72 hours (GDPR Article 33)
- Affected users notified without undue delay
- Incident response playbook in Runbooks

## EU AI Act Compliance

Sentinex is subject to EU AI Act as a provider of AI systems.

### Risk Classification

Most Sentinex use cases are **limited risk**:
- CEO Weekly Brief: transparency obligation (user knows it's AI)
- Strategic analysis: informational support to humans

Some features could be **high risk** if misused:
- Team health signals: could be considered HR decision-making
- Culture monitoring: could be employee surveillance

Mitigation:
- **Culture Pulse addon**: opt-in only, requires explicit employee consent
- **No automated HR decisions**: Sentinex provides signals, humans decide
- **No sentiment analysis of employees**: forbidden unless explicit opt-in

### Transparency

- Users informed when interacting with AI
- AI-generated content labeled
- Data sources and methodology documented

### Human Oversight

- Every strategic decision recommended by AI requires human approval
- Audit trail of AI recommendations
- User can override or ignore AI outputs

## Infrastructure Security

### Server Hardening

- Ubuntu LTS with automatic security updates
- Firewall: only 22 (SSH), 80, 443 open
- SSH: key-based auth only, no passwords
- SSH: fail2ban for brute force protection
- Non-root user for application (`sentinex` user)
- Docker containers run as non-root

### Network Security

- HTTPS everywhere (HSTS with preload)
- Rate limiting at Nginx level
- Per-tenant rate limits in application
- No direct public access to database or Redis

### Dependency Security

- Poetry lockfile committed (`poetry.lock`)
- Dependabot alerts enabled
- Regular updates (monthly at minimum)
- Security patches applied ASAP

## Incident Response

### Detection

- Sentry alerts for unusual error rates
- Hetzner monitoring alerts for resource anomalies
- Manual reports from users

### Response Procedure

1. **Assess**: determine scope and severity
2. **Contain**: stop the incident from expanding
3. **Eradicate**: remove the threat
4. **Recover**: restore services
5. **Review**: post-mortem and prevent recurrence

### Communication

- Internal: team notified via private channel
- External: affected users notified per GDPR
- Public: statement if warranted

## Developer Security

### Code Review

- All changes require review (when team grows)
- Security-sensitive changes require explicit security review
- CI checks for known vulnerable patterns

### Secure Coding

- Input validation on all user inputs
- Output encoding for XSS prevention
- Parameterized queries (Django ORM)
- CSRF protection (Django built-in)
- SQL injection prevention (Django ORM)

### Developer Access

- SSH access limited to necessary developers
- Production access audit-logged
- Developers use their own accounts, never shared credentials

## Security Checklist

Before production launch:
- [ ] All secrets in environment variables, not code
- [ ] HTTPS enabled with valid certificates
- [ ] HSTS header set
- [ ] CSP header configured
- [ ] Session cookies marked Secure and HttpOnly
- [ ] CSRF protection enabled
- [ ] Rate limiting configured
- [ ] Fail2ban running
- [ ] Audit logging working
- [ ] Backup procedure tested
- [ ] Incident response playbook documented
- [ ] GDPR export and delete tested
- [ ] OAuth tokens encrypted at rest
- [ ] PII masking working in LLM calls
- [ ] Tenant isolation tests passing
- [ ] Security.txt file served at /.well-known/security.txt
