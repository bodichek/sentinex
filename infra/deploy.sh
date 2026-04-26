#!/usr/bin/env bash
# Zero-downtime deploy: flip between web_a and web_b behind Nginx.
# Requires docker compose v2, nginx in docker-compose.prod.yml, and the
# upstream target configured in infra/nginx/sentinex.conf.

set -euo pipefail

cd /opt/sentinex

git fetch --all --prune
git reset --hard origin/main

docker compose -f docker-compose.prod.yml build web_a web_b

# Determine currently active upstream
ACTIVE=$(grep -Eo 'server web_[ab]' infra/nginx/sentinex.conf | head -1 | awk '{print $2}')
if [[ "$ACTIVE" == "web_a" ]]; then
    NEW="web_b"
else
    NEW="web_a"
fi

echo "==> active: ${ACTIVE} -> deploying to ${NEW}"

docker compose -f docker-compose.prod.yml up -d "${NEW}" celery_worker celery_beat postgres redis

# Run migrations (idempotent, safe to run repeatedly).
docker compose -f docker-compose.prod.yml exec -T "${NEW}" \
    python manage.py migrate_schemas --shared --noinput
docker compose -f docker-compose.prod.yml exec -T "${NEW}" \
    python manage.py migrate_schemas --noinput

# Health check loop
for i in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T "${NEW}" \
        curl -sf http://localhost:8000/health/ >/dev/null; then
        echo "==> ${NEW} healthy"
        break
    fi
    sleep 2
    if [[ "$i" == "30" ]]; then
        echo "FAIL: ${NEW} did not become healthy — aborting"
        docker compose -f docker-compose.prod.yml stop "${NEW}"
        exit 1
    fi
done

# Swap Nginx upstream and reload
sed -i "s/server web_[ab]:8000/server ${NEW}:8000/" infra/nginx/sentinex.conf
docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

# Grace period, then stop old instance
sleep 10
docker compose -f docker-compose.prod.yml stop "${ACTIVE}" || true

echo "==> deploy complete: ${NEW} is live"
