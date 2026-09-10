#!/usr/bin/env bash
set -euo pipefail
# Use a dump restored FROM OFFSITE to prove recovery, not merely a local backup.
archive=${1:?Usage: restore_test.sh restored-risk.dump}
name="mt5-risk-restore-test-$(date +%s)"
cleanup() { docker rm -f "$name" >/dev/null; }
trap cleanup EXIT
# No host ports, no production mounts, no external network.
docker run -d --name "$name" --network none --memory=256m --cpus=1 --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17-bookworm@sha256:84560e3b9c6874893fc4e2854f5dc3e7c1a37bc9d1dfd7a8c641310ae22ba5ad >/dev/null
for attempt in $(seq 1 30); do
  if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$name" createdb -U postgres risk_restore
docker exec -i "$name" pg_restore -U postgres -d risk_restore --no-owner --exit-on-error < "$archive"
docker exec "$name" psql -U postgres -d risk_restore -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version; SELECT count(*) AS accounts FROM trading_accounts; SELECT count(*) AS commands FROM commands; SELECT count(*) AS audit_events FROM audit_events;'
printf 'Restore test SUCCESS at %s. Record counts and compare with the backup source.\n' "$(date -u +%FT%TZ)"
