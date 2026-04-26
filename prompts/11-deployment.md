# Prompt 11: Production Deployment

## Goal

Finalize production deployment on Hetzner Cloud. Zero-downtime via Docker Compose + Nginx reload, SSL with Let's Encrypt wildcard, Sentry monitoring, backups (basic).

## Prerequisites

- Phases 1–3 complete
- Hetzner server provisioned (CAX31 or similar)
- Domain DNS configured:
  - `A sentinex.<tld>` → server IP
  - `A *.sentinex.<tld>` → server IP
- SSH access to server with user `sentinex`

## Context

This is the ops phase. Getting the code to production, running reliably, observable, recoverable. See `docs/DEPLOYMENT.md`.

## Constraints

- Single server for MVP (not Kubernetes, not multi-server)
- Zero-downtime deploys (two app containers, Nginx switch)
- Let's Encrypt for SSL (wildcard via DNS challenge)
- Sentry for errors (free tier)
- Hetzner monitoring for infrastructure
- Basic backup: manual for now (document procedure, automate later)

## Deliverables

1. `infra/` directory at repo root:
   - `nginx/sentinex.conf` — production Nginx config
   - `docker-compose.prod.yml` — production Docker Compose
   - `deploy.sh` — deployment script
   - `setup-server.sh` — initial server provisioning script
   - `ssl-renew.sh` — SSL renewal script (cron)
2. `Dockerfile.prod` optimized for production:
   - Multi-stage build
   - Non-root user
   - Minimal image size
   - Gunicorn as WSGI server
3. `docker-compose.prod.yml` services:
   - `web_a` (Django via Gunicorn)
   - `web_b` (Django via Gunicorn — second instance for zero-downtime)
   - `celery_worker` (Celery workers)
   - `celery_beat` (Celery Beat scheduler)
   - `postgres` (with persistent volume)
   - `redis` (with persistent volume)
4. Nginx configuration:
   - SSL termination (port 443)
   - HTTP → HTTPS redirect (port 80)
   - HSTS header
   - Wildcard subdomain routing to upstream
   - Upstream `app` points to `web_a` or `web_b`
   - Static file serving from `/opt/sentinex/staticfiles/`
   - Media files from `/opt/sentinex/mediafiles/`
   - Rate limiting zones configured
5. `deploy.sh` script:
   - Detect active container (web_a or web_b)
   - Build new image for inactive container
   - Start inactive container with new code
   - Health check (retry with timeout)
   - Run `migrate_schemas --shared` and `migrate_schemas` (safely)
   - Update Nginx upstream to point to new active
   - `nginx -s reload` (zero-downtime)
   - Stop old container after grace period
   - Rollback on failure
6. `setup-server.sh` script (run once per new server):
   - Install Docker, Docker Compose, Nginx, Certbot
   - Create `sentinex` user with Docker group
   - Clone repo to `/opt/sentinex`
   - Set up firewall (ufw): allow 22, 80, 443
   - Configure fail2ban
   - Disable SSH password auth
7. SSL setup documented:
   - Manual Certbot command for wildcard cert (DNS challenge)
   - Auto-renewal via cron (monthly)
8. Sentry integration:
   - `sentry-sdk[django]` added
   - Configured in `config/settings/prod.py`
   - PII scrubbing enabled
   - Sample rate configured (100% errors, 10% performance)
9. GitHub Actions `deploy.yml`:
   - Triggers on push to `main`
   - SSH to server, runs `deploy.sh`
   - Uses `HETZNER_HOST` and `SSH_PRIVATE_KEY` secrets
10. Health check endpoint:
    - `GET /health/` returns 200 with JSON `{"status": "ok", "version": "..."}`
    - Checks DB and Redis connectivity
11. Management commands for ops:
    - `healthcheck` — runs health checks and prints status
    - `cache_warmup` — pre-warms caches after deploy
12. Documentation:
    - `docs/DEPLOYMENT.md` updated with actual commands used
    - Runbook for common ops tasks

## Acceptance Criteria

- Initial deployment succeeds on fresh Hetzner server
- `https://sentinex.<tld>/` loads (public site)
- `https://demo.sentinex.<tld>/` loads (tenant site)
- SSL certificate valid, A+ on SSL Labs
- Pushing to `main` triggers GitHub Actions deploy
- Deploy completes in under 5 minutes
- Zero-downtime verified: external monitor shows no downtime during deploy
- Health endpoint returns 200
- Sentry receives test error
- Hetzner monitoring shows healthy metrics
- Rollback works (simulate failed deploy)

## Next Steps

After this prompt, proceed to `12-pilot-onboarding.md`.

## Notes for Claude Code

- Gunicorn config: use `gevent` or `uvicorn` workers for better async handling; `--workers N --threads T`
- Environment: `.env` file on server at `/opt/sentinex/.env`, permissions 600
- Static files: `collectstatic --noinput` during container build
- Media files: mount volume `/opt/sentinex/mediafiles:/app/mediafiles`
- Postgres persistent volume mounted to `/var/lib/postgresql/data`
- Redis persistent volume mounted to `/data` (for AOF)
- Nginx zero-downtime trick: use `upstream` block with variable, reload picks new target
- Alternative zero-downtime: blue/green via port switch; pick whichever is simpler
- Sentry DSN in `.env` as `SENTRY_DSN`
- For SSL: `certbot certonly --manual --preferred-challenges=dns -d 'sentinex.<tld>' -d '*.sentinex.<tld>'`
- Fail2ban config: SSH jail, 5 failures in 10 minutes → ban 1 hour
