# Operations runbook

## Normal checks

- `GET /healthz`: process alive. `GET /readyz`: database/migration access. Compose health must be healthy.
- Dashboard: account state, heartbeat, EA version, execution toggle, exact symbol mappings and recent commands. ONLINE means <5 seconds, STALE 5–10, OFFLINE >10. Trading requests require a heartbeat within 10 seconds. Unsupported margin mode remains visible.
- Structured logs contain user/account/agent/command IDs and transition events. Audit records include immutable submitted result bodies/retcodes at the application layer. Broker-confirmed data is reported by the EA, not independently verified by the server.
- Outbox failures log `TELEGRAM_DELIVERY_FAILED` without error text that might contain tokens. Retries back off to 60 seconds; notifications older than ten minutes are scrubbed/discarded. A stale Confirm button remains invalid at the server.
- Inspect backup status JSON and systemd journal daily. A successful archive creation alone is not a recovery test.

## Agent offline / backend outage

Verify MT5 connection, allowed WebRequest URL, certificate, terminal/account permissions and logs. The agent backs off to 30 seconds plus jitter; it never opens a listener. Existing broker stops remain independent of the backend. Expired PENDING commands will not be delivered after recovery. A leased execution without a result blocks new work; do not blindly repeat a close.

## ACCOUNT_MISMATCH / REPAIR_REQUIRED

The user switched account/server or the installation differs. Stop the EA and verify login/server. Merely switching back does not clear the latch. Revoke/re-pair after confirming there is no unresolved leased execution. Never treat account number as authentication.

## BLOCKED_UNCERTAIN / interrupted terminal / broker timeout

1. Stop accepting new risk requests for that account; retain the terminal journal, recent IDs, Experts log, command and audit rows.
2. Let the original EA resend its persisted DONE result where possible. The server accepts a late identical result. If the EA restarted during STARTED it reports UNCERTAIN; it will not resume broker sends. A different session cannot inherit a leased execution.
3. Inspect MT5 **current positions and broker deal history**. Compare each ticket/position identifier, exit deal, SL/TP, volume, retcode and operation time. An absent position alone does not prove this command closed it.
4. Record evidence JSON outside public storage, with `operator`, `checked_at_utc`, `broker_deals` (or explicit checked/no-deals explanation), and `conclusion`. Record any completed volume and manual corrections. Do not include broker passwords or tokens.
5. Only after inspection, a privileged operator may run:

```bash
# From a configured checkout with DB access; path is to your real evidence JSON.
.venv/bin/python tools/reconcile.py <command-uuid> \
  --evidence /secure/incident-evidence.json --acknowledge-broker-history-checked
```

The utility accepts only UNCERTAIN commands, takes the account lock, marks the operation CANCELLED/reconciled, clears the block, and appends `OPERATOR_RECONCILED` evidence. It sends no trade. This is deliberately absent from the public dashboard/API. Reconcile or archive the local journal too; preserve evidence before deleting any local state. Never use the utility merely to bypass a busy account. Revoked credentials cannot submit results; those incidents need this procedure.

## Revoke / leaked token

Use dashboard revoke. New polls immediately fail authentication, but an already delivered command can continue until its local deadline; revocation cannot recall a broker request. Leased executions become UNCERTAIN. Pair a new installation only after reconciliation. If the Telegram bot token leaked, rotate it and the webhook secret, invalidate web sessions (`web_sessions`), expire old pairing codes and clear undelivered encrypted pairing notices; their encryption key derived from the old token is no longer valid. Re-register webhook, then issue fresh `/link` codes.

## Broker rejection / partial result

Review position-level machine codes and retcodes in `command_results` and the audit. `SKIPPED_NOT_ENOUGH_DISTANCE` / `FREEZE_LEVEL` are expected when price is too close; no alternative unsafe stop is substituted. `BROKER_REJECTED` means the request was not accepted. `EXECUTION_UNCERTAIN` means the server must not infer failure or retry. BE might protect fewer lots than requested; close can underfill due to rounding, partial broker fill, or lot restrictions. Ask for a fresh preview only after the prior outcome is resolved.

## Maintenance and retention

The two-second sweeper expires queues and prunes expired sessions, old pairing codes, seven-day webhook IDs and rate buckets idle for a day. Delivered outbox payloads are scrubbed. Command/results/audits are retained; define a user privacy and audit-retention policy before commercial rollout. Outbox row metadata can be archived during periodic DB maintenance. Run PostgreSQL vacuum normally; monitor disk and backup age. Keep a release/incident log tied to command IDs. No notification content, broker login or token belongs in routine debug logs.
