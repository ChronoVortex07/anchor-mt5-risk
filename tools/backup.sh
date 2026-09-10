#!/usr/bin/env bash
set -euo pipefail
umask 077
# systemd loads project config plus RESTIC_REPOSITORY / RESTIC_PASSWORD_FILE.
: "${RISK_PROJECT_DIR:?}" "${RISK_BACKUP_DIR:?}" "${RESTIC_REPOSITORY:?}" "${RESTIC_PASSWORD_FILE:?}"
mkdir -p "$RISK_BACKUP_DIR"
exec 9>"$RISK_BACKUP_DIR/backup.lock"
flock -n 9 || exit 0
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$RISK_BACKUP_DIR/risk-$stamp.dump"
status="$RISK_BACKUP_DIR/status.json"
trap 'printf "{\"status\":\"FAILED\",\"at\":\"%s\"}\n" "$(date -u +%FT%TZ)" > "$status"' ERR
compose=(docker compose --env-file "$RISK_PROJECT_DIR/.env" -p "${RISK_COMPOSE_PROJECT:-mt5-risk-prod}" -f "$RISK_PROJECT_DIR/infra/compose.yaml")
"${compose[@]}" exec -T postgres pg_dump -U risk -d risk --format=custom --compress=6 > "$archive.tmp"
"${compose[@]}" exec -T postgres pg_restore --list < "$archive.tmp" > /dev/null
mv "$archive.tmp" "$archive"
sha256sum "$archive" > "$archive.sha256"
# Restic encrypts before sending offsite. init repository once before scheduling.
restic backup "$archive" "$archive.sha256" --tag mt5-risk-postgres
restic forget --group-by host,tags --tag mt5-risk-postgres --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
find "$RISK_BACKUP_DIR" -maxdepth 1 -type f -name 'risk-*.dump*' -mtime +7 -delete
printf '{"status":"SUCCESS","at":"%s","archive":"%s"}\n' "$(date -u +%FT%TZ)" "$(basename "$archive")" > "$status"
printf 'Backup stored offsite: %s\n' "$(basename "$archive")"
