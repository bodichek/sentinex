#!/usr/bin/env bash
# Sentinex deploy: pull → build → up → migrate → collectstatic → health-check.
# Run on the Hetzner host as the sentinex user from /opt/sentinex.

set -euo pipefail

cd /opt/sentinex

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> git pull"
git pull origin main

echo "==> build web image"
$COMPOSE build web

echo "==> bring stack up"
$COMPOSE up -d

echo "==> migrate shared schema"
$COMPOSE exec -T web python manage.py migrate_schemas --shared --noinput

echo "==> migrate tenant schemas"
$COMPOSE exec -T web python manage.py migrate_schemas --noinput

echo "==> collectstatic"
$COMPOSE exec -T web python manage.py collectstatic --noinput

echo "==> health check"
for i in $(seq 1 30); do
    if curl -fsS http://localhost/health/ >/dev/null; then
        echo "==> deploy ok"
        exit 0
    fi
    sleep 2
done

echo "!! health check failed" >&2
exit 1
