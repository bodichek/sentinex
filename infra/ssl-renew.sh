#!/usr/bin/env bash
# Wildcard SSL renewal with DNS challenge. Schedule via cron monthly.
#
# Initial issuance (run manually once):
#   certbot certonly --manual --preferred-challenges=dns \
#       -d 'sentinex.example' -d '*.sentinex.example' \
#       --agree-tos -m ops@sentinex.example
#
# Renewal (cron):
#   0 3 1 * *  /opt/sentinex/infra/ssl-renew.sh >> /var/log/sentinex-ssl.log 2>&1

set -euo pipefail

certbot renew --quiet
docker compose -f /opt/sentinex/docker-compose.prod.yml exec -T nginx nginx -s reload
