# Changelog

## v0.2.0-alpha.1 — 2026-09-13

- Added a separate native `LocalRiskPanel` EA with no Telegram, backend,
  database, pairing or WebRequest dependency.
- Added current-symbol exposure, 25/50/100% targets, side-specific BE actions
  and worst-cost BUY/SELL/BOTH close actions.
- Added expiring previews, refreshed-plan reconfirmation, preview-only default
  and an independent live-account execution lock.
- Added a deterministic local-panel source package and dedicated CI/release
  artifact without changing the remote `BreakEvenAgent` package.
- Added end-to-end Windows installation, checksum, compilation, demo execution,
  troubleshooting and multi-device testing instructions.
- MQL5 compilation and broker execution remain unverified by the publisher.

## v0.1.0-alpha.2 — 2026-09-13

- Dashboard navigation switches views and explains authentication for signed-out Accounts/Activity pages.
- Added current BotFather Allowed URLs setup help beside sign-in; set the light color scheme and clip iframe corners to match the login button.
- EA 0.11 reports MT5 WebRequest error codes and known pairing rejection reasons without logging credentials.
- Reject placeholder/path ApiUrl settings with actionable instructions; pairing timeout is five seconds while polling stays at two seconds.
- Added browser regression tests and connection troubleshooting instructions.
- MQL5 changes remain uncompiled by the publisher; no broker execution validation is claimed.


## v0.1.0-alpha.1 — 2026-09-11

Initial MIT-licensed source prerelease:

- Telegram `/link`, `/be`, `/close` with expiring preview/confirmation.
- PostgreSQL pairing, agent authentication/account/session binding, durable queue and audit.
- MQL5 EA source, deterministic planner tests and Python fake agent.
- Dashboard, Docker Compose and operations/backup documentation.
- Telegram operator setup utility with identity/webhook verification and read-only checks.
- Downloadable EA source ZIP with all includes, license and installation instructions.

MQL5 compilation and real broker execution are not verified. No precompiled EX5 or hosted Telegram identity is included. See the validation report and demo checklist.
