# Skill: Deploy

Use this skill when deploying Sentinex to production or staging.

## When to Use

- Rolling out new features to production
- Hot-fixing bugs
- Setting up a fresh environment
- Upgrading infrastructure

## Deployment Channels

1. **Development**: local Docker Compose
2. **Staging**: Hetzner server, auto-deployed from `main` branch
3. **Production**: Hetzner server, manual trigger

## Prerequisites

- SSH access to target server
- GitHub Actions secrets configured
- `.env` file on server up to date
- Database backups verified working (when backups are set up)

## Automated Deploy (Recommended)

### Staging

Push to `main` automatically deploys to staging via GitHub Actions.

```bash
git push origin main
```

Monitor:
- GitHub Actions workflow: https://github.com/<owner>/sentinex/actions
- Sentry for errors
- Staging server health endpoint

### Production

Manual trigger (GitHub Actions workflow dispatch):

1. Go to Actions → Deploy
2. Select "Run workflow"
3. Choose branch (usually `main`)
4. Confirm

## Manual Deploy (Fallback)

If CI/CD is broken:

```bash
# SSH to server
ssh sentinex@<server-ip>
cd /opt/sentinex

# Pull latest
git fetch
git checkout <branch>
git pull

# Run deploy script
bash infra/deploy.sh
```

## Zero-Downtime Strategy

Sentinex uses two app container instances behind Nginx.

### Flow

1. Identify active container (say `web_a`)
2. Build new image for inactive container (`web_b`)
3. Start `web_b` with new code
4. Wait for health check
5. Run safe migrations (backward-compatible only)
6. Switch Nginx upstream to `web_b`
7. Reload Nginx (no downtime)
8. Stop `web_a`

### What Makes It Zero-Downtime

- Nginx reload is non-disruptive (keeps existing connections)
- Both containers share database (no migration conflicts if migrations are backward-compatible)
- Health check before switch (catches broken deploys)
- Can rollback by switching back

## Pre-Deploy Checklist

Before hitting deploy:

- [ ] Tests pass in CI
- [ ] Migrations are backward-compatible
- [ ] No secrets in code (checked in CI)
- [ ] Critical features manually tested in staging
- [ ] Deploy window appropriate (not during high load or critical tenant activity)
- [ ] Rollback plan clear
- [ ] Relevant team members aware

## Post-Deploy Verification

After deploy completes:

1. Health endpoint returns 200: `curl https://sentinex.<tld>/health/`
2. No spike in errors in Sentry
3. Can log in as test user
4. Critical user journey works (e.g., weekly brief generation)
5. Celery workers processing tasks
6. No failing scheduled tasks

## Rollback

If deploy breaks production:

### Quick Rollback

```bash
ssh sentinex@<server-ip>
cd /opt/sentinex

# Switch back to previous commit
git reset --hard HEAD~1

# Re-run deploy
bash infra/deploy.sh
```

### Migration Rollback

If a migration broke things:

```bash
# Identify problem migration
docker compose -f docker-compose.prod.yml exec web python manage.py showmigrations

# Revert to previous
docker compose -f docker-compose.prod.yml exec web python manage.py migrate_schemas <app> <previous_migration>
```

Note: destructive migrations can't always be reverted cleanly. Prevention better than cure.

## Deploying Migrations

### Safe Migrations (Can Deploy During Business Hours)

- Adding nullable column
- Adding column with default
- Adding index (CONCURRENTLY)
- Dropping unused column (if code no longer uses it)
- Changing table comments

### Risky Migrations (Deploy During Low-Traffic Window)

- Adding non-nullable column with computed default
- Renaming columns (use two-step approach)
- Changing column types
- Adding index on large table (non-concurrent)
- Data migrations on large tables

### Dangerous Migrations (Require Downtime)

- Dropping column still in use
- Renaming column in one step
- Foreign key constraint changes
- Anything that locks a table

For dangerous migrations:
1. Announce maintenance window to users
2. Disable traffic (maintenance page)
3. Run migration
4. Verify
5. Restore traffic

## Environment Configuration

### First-Time Server Setup

See `docs/DEPLOYMENT.md` for full server setup procedure.

### Updating Environment Variables

```bash
ssh sentinex@<server-ip>
cd /opt/sentinex
nano .env
# Edit values
docker compose -f docker-compose.prod.yml restart web_a web_b celery_worker
```

### Restarting Services

```bash
# Restart app containers
docker compose -f docker-compose.prod.yml restart web_a web_b

# Restart Celery workers
docker compose -f docker-compose.prod.yml restart celery_worker

# Restart everything (brief downtime)
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## Monitoring After Deploy

### First 15 Minutes

- Watch Sentry for new errors
- Watch Hetzner monitoring for resource spikes
- Watch application logs
- Test user-facing paths

### First Hour

- Verify scheduled tasks run correctly
- Verify integrations still working (Google Workspace OAuth)
- Verify billing calculations unchanged

### First 24 Hours

- Monitor tenant-specific issues
- Check user reports
- Review log patterns

## Common Issues

### Deploy Fails at Migration

Check migration logs, likely:
- Missing column reference
- Data that doesn't fit new constraint
- Permission issue on schema

Fix locally, amend migration, redeploy.

### Static Files Not Loading

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

### Celery Tasks Not Running

```bash
# Check worker status
docker compose -f docker-compose.prod.yml logs celery_worker | tail -100

# Check Redis connection
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

### SSL Certificate Expired

Let's Encrypt cert expired (shouldn't happen with auto-renewal):

```bash
certbot renew
systemctl reload nginx
```

## Disaster Recovery

### Server Completely Down

1. Spin up new Hetzner server
2. Restore from Hetzner backup (if available)
3. Or: fresh deploy from GitHub
4. Restore database from backup
5. Update DNS to point to new server
6. Notify users

### Database Corruption

1. Stop app (put up maintenance page)
2. Restore database from latest backup
3. Identify missing data (since backup)
4. Recover from logs if possible
5. Restart app
6. Communicate to affected users

### Security Incident

Follow `docs/SECURITY.md` incident response procedure.

## Verification Checklist

After any deploy:

- [ ] Health endpoint returns 200
- [ ] Can log in as user
- [ ] Core flow works (addon usage)
- [ ] No new errors in Sentry
- [ ] Celery tasks processing
- [ ] Scheduled tasks running
- [ ] Integrations (OAuth) still working
