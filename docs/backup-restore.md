# Backup, offsite retention and recovery

`tools/backup.sh` creates a PostgreSQL custom-format compressed dump, verifies its archive index, writes a SHA-256 checksum, sends the dump/checksum to an **encrypted offsite Restic repository**, and applies retention. It reports success only after remote backup succeeds. Archive index/checksum verification proves readability, not application-level recovery; perform the restore test below.

Restic and Docker CLI are operator-host dependencies. Restic may use SFTP or S3-compatible offsite storage; do not put the only copy on this VPS. Protect the repository key separately from the VPS and its backups. The script uses `set -euo pipefail`, mode 0600 files, `flock`, and writes `status.json` on success/failure. Systemd's job status/journal also captures failure. No offsite destination or credentials were provided during implementation, so remote transfer and scheduling have not been activated.

## Configure daily backup

1. Install Restic on the operations host. Create an offsite repository and initialize it once with `restic init`.
2. Create `/etc/mt5-risk-backup.env` mode 0600:

```dotenv
RISK_PROJECT_DIR=/opt/mt5-risk
RISK_BACKUP_DIR=/var/backups/mt5-risk
RISK_COMPOSE_PROJECT=mt5-risk-prod
RESTIC_REPOSITORY=sftp:backup-user@offsite.example:/srv/backups/mt5-risk
RESTIC_PASSWORD_FILE=/etc/mt5-risk-restic-password
```

Use a dedicated SSH key/account and pin the offsite host key. Keep the repository password file 0600. Optional provider credentials belong in this protected environment, never Git. `RISK_PROJECT_DIR/.env` holds the Compose configuration; pg_dump runs inside the DB container without a password in the command line.

3. Copy/adapt `infra/mt5-risk-backup.service` and `.timer` into systemd; ensure ExecStart matches the deployment path. Enable the timer only after a manual backup and restore test succeed:

```bash
systemctl daemon-reload
systemctl start mt5-risk-backup.service
systemctl status mt5-risk-backup.service
systemctl enable --now mt5-risk-backup.timer
systemctl list-timers mt5-risk-backup.timer
```

The timer runs daily at 03:20 UTC with up to 15 minutes of jitter; missed runs are resumed. Retention: local dumps seven days, remote seven daily/four weekly/six monthly snapshots. Changing it is an operator decision tied to audit/privacy requirements. Inspect `status.json` and alert on last success older than 26 hours. The current service does not send an external operations alert automatically; connect systemd failure notification to your chosen monitoring channel.

## Periodic restore test

At least monthly, and before upgrades:

```bash
restic snapshots --tag mt5-risk-postgres
# Select the intended snapshot; do not overwrite the deployment directory.
restic restore <snapshot-id> --target /tmp/risk-offsite-recovery
# Locate the restored dump and checksum under the reconstructed source path.
sha256sum /tmp/risk-offsite-recovery/<path>/risk-<timestamp>.dump
# Compare with the saved .sha256 digest (its original absolute pathname differs).
bash tools/restore_test.sh /tmp/risk-offsite-recovery/<path>/risk-<timestamp>.dump
```

The test script creates a temporary PostgreSQL container with **no network or host ports**, restores with `--exit-on-error --no-owner`, queries Alembic version and account/command/audit counts, and always removes the temporary container. Compare counts and sample known command/result relationships against your backup-time record. Record elapsed time, snapshot ID, checksum, revision and counts in the operations log. For stronger validation, run read-only application queries against the restored copy. Never attach an executing EA to the restore-test database.

The implementation was tested with a local development dump restored into a separate temporary database. That validates the restore mechanics and schema, not offsite credentials, remote retention or production data recoverability.

## Actual recovery

1. Stop backend/ingress and stop the EAs or keep execution disabled. Preserve failed-database files and terminal journals as incident evidence.
2. Provision a **new empty** PostgreSQL volume/service. Restore the chosen verified offsite dump into a fresh database with `pg_restore --no-owner --exit-on-error`; do not drop a production database casually to make restore commands work.
3. Verify migration version, table counts, recent command/result integrity and account ownership. Revoke sessions/tokens if the incident could have exposed them. Restoring a backup can resurrect previously revoked credentials: review revocations against external incident records and rotate agent credentials where uncertain.
4. Run backend migrations only if the target application revision requires them. Let expired commands expire. Reconcile **every** execution that was pending/leased around the incident using terminal journals and broker deal history. Database rollback must not be interpreted as broker rollback.
5. Validate health and HTTPS, re-register the webhook if necessary, then reconnect one demo EA in preview mode before restoring live service. Record recovery point and duration. Never automatically retry historical close commands.
