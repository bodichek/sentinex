# Deployment Guide

## Overview

Sentinex is deployed on Hetzner Cloud using Docker Compose with Nginx zero-downtime reload strategy.

## Production Environment

### Server Specifications

MVP: single Hetzner Cloud server (CAX21 or similar, adjustable based on load).

Scale up when needed:
- 1–10 tenants: CAX21 (4 vCPU, 8GB RAM)
- 10–30 tenants: CAX31 (8 vCPU, 16GB RAM)
- 30+ tenants: dedicated AX52 or split into multiple servers

### Server Setup (one-time)

SSH access required. Run as root or user with sudo.

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Install Nginx
apt install -y nginx

# Install Certbot for SSL
apt install -y certbot python3-certbot-nginx

# Create app user
useradd -m -s /bin/bash sentinex
usermod -aG docker sentinex

# Create app directory
mkdir -p /opt/sentinex
chown sentinex:sentinex /opt/sentinex
```

### DNS Configuration

Required DNS records (at registrar):
- `A sentinex.<tld>` → server IP
- `A *.sentinex.<tld>` → server IP (wildcard for tenant subdomains)

### SSL Certificate

Use Let's Encrypt with wildcard certificate (requires DNS challenge):

```bash
certbot certonly --manual --preferred-challenges=dns \
  -d sentinex.<tld> \
  -d '*.sentinex.<tld>' \
  --agree-tos \
  --email admin@sentinex.<tld>
```

Follow DNS challenge instructions. Certificate renewed manually or via DNS API automation.

### Nginx Configuration

See `infra/nginx/sentinex.conf` in the repo. Copy to `/etc/nginx/sites-available/sentinex`:

```bash
ln -s /etc/nginx/sites-available/sentinex /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Key features:
- SSL termination
- Wildcard subdomain routing
- Two upstream servers for zero-downtime
- Static file serving
- Rate limiting

### Application Deployment

#### Initial deploy

```bash
# SSH to server as sentinex user
ssh sentinex@<server-ip>
cd /opt/sentinex

# Clone repo
git clone git@github.com:<owner>/sentinex.git .

# Create production .env
cp .env.example .env
# Edit .env with production values
# IMPORTANT: use strong SECRET_KEY, real API keys, production DB credentials

# Build and start services
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate_schemas --shared
docker compose -f docker-compose.prod.yml exec web python manage.py migrate_schemas

# Collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Create superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

#### Required environment variables

Beyond the standard Django secrets / DB / Redis / Anthropic-OpenAI keys
documented in `.env.example`, production deploys that enable the Workspace
DWD connector need:

```bash
# Service Account JSON — file path preferred
GOOGLE_WORKSPACE_SA_JSON_PATH=/var/secrets/sentinex-sa.json
# (or inline JSON in container envs)
# GOOGLE_WORKSPACE_SA_JSON={"type":"service_account",...}

GOOGLE_WORKSPACE_DOMAIN=acme.cz
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@acme.cz

# Knowledge ingestion (defaults are sane; override only if needed)
KNOWLEDGE_EMBEDDING_MODEL=text-embedding-3-small
KNOWLEDGE_EMBEDDING_DIMENSIONS=1536
KNOWLEDGE_CHUNK_SIZE_TOKENS=800
KNOWLEDGE_CHUNK_OVERLAP_TOKENS=100
KNOWLEDGE_MAX_FILE_BYTES=20000000
KNOWLEDGE_STUB_MODE=False
```

The SA JSON file should be **read-only for the sentinex user**, not
checked in, and rotated on the same cadence as other secrets.
See `docs/GOOGLE_WORKSPACE_DWD.md` for end-to-end setup.

#### Celery Beat (scheduled jobs)

`config/settings/base.py` ships with a `CELERY_BEAT_SCHEDULE`:

| Task | Schedule |
|------|----------|
| `data_access.knowledge_incremental_dispatch` | every 5 min |
| `data_access.workspace_directory_dispatch`   | daily |
| `data_access.workspace_audit_dispatch`       | hourly |
| `data_access.sync_slack_dispatch`            | every 6 h |

Production must run a single Beat process (not multiple instances —
django-celery-beat uses Postgres locks but a single instance is safest):

```bash
docker compose -f docker-compose.prod.yml up -d celery-beat
```

Workers and Beat read the same Redis broker as the web instances.

#### Zero-downtime deploy

Production runs two app container instances (`web_a` and `web_b`). Nginx upstream switches between them.

Deploy script (`infra/deploy.sh`):

```bash
#!/bin/bash
set -e

cd /opt/sentinex

# Pull latest code
git pull origin main

# Determine which container is currently active
ACTIVE=$(cat .active_container 2>/dev/null || echo "web_a")
INACTIVE=$([ "$ACTIVE" = "web_a" ] && echo "web_b" || echo "web_a")

echo "Deploying to $INACTIVE..."

# Build new image
docker compose -f docker-compose.prod.yml build $INACTIVE

# Start inactive container with new code
docker compose -f docker-compose.prod.yml up -d --no-deps $INACTIVE

# Wait for health check
sleep 10
if ! docker compose -f docker-compose.prod.yml exec -T $INACTIVE curl -f http://localhost:8000/health/; then
  echo "Health check failed!"
  exit 1
fi

# Run migrations (safe, backward-compatible migrations only)
docker compose -f docker-compose.prod.yml exec -T $INACTIVE python manage.py migrate_schemas --shared
docker compose -f docker-compose.prod.yml exec -T $INACTIVE python manage.py migrate_schemas

# Switch Nginx upstream
sed -i "s/server web_$ACTIVE/server web_$INACTIVE/g" /etc/nginx/sites-available/sentinex
# Actually this should use upstream file switch; implementation detail

nginx -s reload

# Record new active
echo $INACTIVE > .active_container

# Stop old container (after brief grace period)
sleep 5
docker compose -f docker-compose.prod.yml stop $ACTIVE

echo "Deploy complete. Active: $INACTIVE"
```

This script is simplified. Production version handles edge cases (failed migrations, rollback, etc.).

### GitHub Actions Deploy

`.github/workflows/deploy.yml` triggers on push to `main`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Hetzner
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: sentinex
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/sentinex
            bash infra/deploy.sh
```

Required GitHub secrets:
- `HETZNER_HOST` — server IP or hostname
- `SSH_PRIVATE_KEY` — SSH key with deploy access

## Monitoring

### Sentry

Error tracking. Free tier sufficient for MVP.

Setup:
1. Create Sentry project at sentry.io
2. Add `SENTRY_DSN` to `.env`
3. Errors automatically reported

### Hetzner Monitoring

Built-in server monitoring. Access via Hetzner Cloud Console.

Monitors:
- CPU, RAM, disk usage
- Network traffic
- Alerts via email

### Logs

Application logs:
- Django logs → stdout → Docker logs
- Access via `docker compose logs -f web_a`
- Aggregation not set up in MVP (add Better Stack or similar later)

## Backups

**Not set up in MVP.** To be added later.

When added:
- Daily pg_dump of all schemas
- Upload to Hetzner Storage Box
- 30-day retention
- Test restore quarterly

## Rollback

If deploy fails:

```bash
cd /opt/sentinex

# Revert git
git reset --hard HEAD~1

# Redeploy
bash infra/deploy.sh
```

If migration breaks production:

```bash
# Migrations must be backward-compatible in MVP.
# If a migration breaks, manual intervention required:
docker compose exec web python manage.py migrate_schemas <app> <previous_migration>
```

Plan migrations carefully — avoid destructive changes without dual-write period.

## Scaling

### Vertical scaling (current path)

Upgrade Hetzner server to larger size. Minimal downtime.

### Horizontal scaling (when needed)

When single server insufficient:
1. Separate database server (Hetzner Managed PostgreSQL or dedicated server)
2. Multiple app servers behind Hetzner Load Balancer
3. Dedicated Celery worker server
4. Redis cluster

Not before 50+ tenants.

## Security

- SSL everywhere (HSTS enabled)
- Nginx rate limiting per tenant and per IP
- Django security middleware enabled
- `.env` file permissions: 600 (read-only by owner)
- SSH key authentication only (no password)
- Firewall: only ports 22, 80, 443 open
- Fail2ban for SSH brute force protection

## Disaster Recovery

### Server failure

- Hetzner backup (paid feature, recommended for production)
- DNS can be repointed to new server
- Deploy fresh from GitHub

### Database corruption

- Restore from backup (when backups are set up)
- Worst case: restore from latest Hetzner snapshot

### Security incident

1. Rotate all secrets (new SECRET_KEY, API keys, OAuth tokens)
2. Force logout all users (clear Redis sessions)
3. Audit logs for suspicious activity
4. Notify affected tenants per GDPR requirements

## Maintenance Windows

- Minimize required downtime through zero-downtime deploys
- Schedule disruptive changes (major migrations, server upgrades) for weekends
- Notify tenants via email 48 hours ahead
