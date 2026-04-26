#!/usr/bin/env bash
# Container entrypoint: wait for Postgres, run shared migrations, exec gunicorn.

set -euo pipefail

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-sentinex}"

echo "==> waiting for postgres at ${DB_HOST}:${DB_PORT}"
for _ in $(seq 1 30); do
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
        echo "==> postgres ready"
        break
    fi
    sleep 1
done

echo "==> migrate shared schema"
python manage.py migrate_schemas --shared --noinput

echo "==> exec: $*"
exec "$@"
