# Implementation and validation report

Initial implementation validation: 2026-09-10. Project: Anchor MT5 Risk. This report distinguishes executable test evidence from unverified broker behavior.

## Implemented

- FastAPI, SQLAlchemy 2, Pydantic, aiogram and PostgreSQL backend with three explicit Alembic migrations.
- Separate user/account/agent records; one-use expiring hashed pairing codes, 256-bit hashed agent tokens, revocation and account/installation/session binding.
- Durable account-serialized queue, partial unique in-flight constraint, short fixed deadlines, expiring confirmations, idempotent results, audit and encrypted/scrubbed pairing notification outbox.
- Exactly three Telegram commands: `/link`, `/be`, `/close`, including optional percentages, explicit BE side selection, inline confirmations/cancellation/account selection.
- Volume-based Decimal reference planner and fake EA for both operations, including close worst-cost ordering, gross mixed-side volume and partial final ticket.
- MQL5 source with original bounded JSON parser, outbound HTTPS timer polling, local credential persistence, per-start session ID, STARTED/DONE journal, dry-run default, pure planner tests, narrow SLTP and position-bound close executor.
- React/TypeScript dashboard: signed Telegram login, account state, exact mappings, selection, command history and explicit revoke confirmation.
- Local development Compose, existing-Caddy overlay, standalone HTTPS Compose, pinned base images/dependency locks, health checks, structured logs, backup/restore scripts and systemd templates.
- Architecture, protocol, threat model (18 required scenarios), installation/deployment/runbook, recovery procedures and demo checklist.

## Tests passed

- **51 backend/domain tests against PostgreSQL 17**, including real row-lock races, session fencing and complete simulated Telegram webhook flow. Final suite: 51 passed in 2.81 seconds. No PostgreSQL concurrency tests skipped.
- **3 Chromium browser smoke tests**: signed-out onboarding; authenticated fixture accounts/history/mapping/revoke UI at 1440px and 390px. Final browser suite: 3 passed. Screenshots use mocked account data, not broker accounts.
- Ruff lint and format checks (explicit project config); Python byte compilation; Prettier source-format check; TypeScript check and Vite production build.
- Docker multi-stage image build and development stack startup; `/healthz` and `/readyz` healthy on server-local `127.0.0.1:18089`.
- Alembic upgrade, full downgrade/re-upgrade on disposable `risk_test`, and `alembic check` with no schema differences.
- Development/standalone-production/existing-edge Compose configuration validation; Caddy configuration validation.
- Shell syntax checks for backup/restore scripts; local compressed PostgreSQL dump restoration in a separate network-isolated temporary container, with migration/table queries (latest rehearsal: revision `f9eb2d12038e`, 1 synthetic account, 2 commands, 8 audit events). Offsite recovery remains a separate gate.

Test dependencies currently emit two non-failing deprecation warnings from Starlette's httpx TestClient and AnyIO portal alias. These do not invalidate the passing assertions; dependency migration is future maintenance.

The initial non-root Docker startup permission error was corrected with explicit COPY ownership. A browser assertion was corrected to match whitespace in the accessible heading. Neither failure is left unresolved.

## Tests not runnable / not performed

- MetaEditor compilation, MQL5 script execution and broker demo execution: no Windows MT5/MetaEditor/demo account was available. The EA source has been reviewed but **is not claimed to compile**.
- Actual Telegram webhook delivery, Telegram Login Widget/domain integration and real inline button interactions: no bot token/webhook/public-host configuration was supplied. Backend tests use synthetic updates and signatures; no messages were sent externally.
- Public TLS certificate issuance, shared-gateway changes, firewall/SSH deployment: configuration supplied and locally validated; no public deployment was requested/configured.
- Offsite Restic transfer/retention, systemd timer activation, real offsite restore and external failure alerting: no remote repository or credentials supplied. Local restore tests do not certify offsite recoverability.
- The original validation was local. Public repository CI is reported separately in GitHub Actions.

## Known limitations and security-sensitive assumptions

See [remaining risks](remaining-risks.md) for the full list. Key assumptions: broker evidence is reported by the EA; local machine administrators can bypass EA controls; the narrow close authority can realize losses and increase net directional exposure; MT5 trade operations cannot atomically compare broker state with a previous read; journal/broker uncertainty requires deliberate reconciliation. DB audit is append-only in application behavior, not protected from its privileged DB owner. Proxy forwarding must be trusted for rate-limit attribution.

## Manual MT5 validation and next milestone

Compile the EA and PlannerTests in MetaEditor, configure staging HTTPS/Telegram, then complete [the demo-account checklist](demo-checklist.md) with broker retcodes/deals and restart/fault evidence. Execution defaults to **false**. Live readiness is not established by this delivery.

## Public source release

The open-source repository and EA source archive are distributed separately from operator credentials and deployment state. See [Telegram setup](telegram-setup.md), [trader installation](trader-quickstart.md) and the GitHub Actions runs for release validation. No compiled MQL5 binary or configured hosted Telegram identity is claimed by this source release.

## Open-source distribution checks — 2026-09-11

- Expanded PostgreSQL suite: **65 tests passed** (initial 51 plus Telegram setup and EA archive checks).
- Setup helper verifies bot identity, supports non-mutating checks and preserves queued updates unless explicitly told to discard them.
- EA source packaging is deterministic, includes all MQL5 dependencies/license/install instructions, and excludes credentials, local journals and compiled binaries.
- The `cv_mt5_bot` identity was verified against Telegram and its webhook registered at `https://mt5.chronovortex.dev/v1/telegram/webhook`. Telegram reported zero pending updates and no delivery error at activation. Public `/healthz` and `/readyz` returned HTTP 200; unauthenticated webhook and agent poll submissions returned HTTP 401. This validates deployment and authentication boundaries, not a real-user Telegram-to-MT5 execution. Credentials are excluded from the public repository.

## Connection follow-up — 2026-09-13

- Public `/healthz` returned HTTP 200. An empty POST to `/v1/agent/pair` reached backend validation and returned HTTP 422; no real pairing code was consumed by the probe.
- The user supplied an MT5 `Pairing failed. HTTP -1` log. This establishes a WebRequest failure without an HTTP response, not a rejected pairing code. The original EA omitted `GetLastError()`, so the exact terminal-side cause remains unconfirmed.
- EA 0.11 now logs the numeric MQL network error and known backend rejection codes. Static review only: MetaEditor and MT5 execution are unavailable here.
- Dashboard navigation and signed-out instructions were corrected; Telegram's legacy widget remains in use. After updating BotFather Allowed URLs, the user and a browser inspection confirmed the login button renders without the domain error. A completed real-user login remains unverified. No successful dashboard authentication is claimed from mocked browser tests.
- TypeScript/Vite build, Prettier, Ruff and 14 distribution/setup tests passed. Browser checks cover signed-out navigation, authenticated views with mocked account data, and desktop/mobile layouts.

External browser runs encountered intermittent loading/network errors, including `net::ERR_NETWORK_CHANGED`. The full five-test browser suite passed against the deployed container over its private network; public endpoint probes and both navigation regression cases also passed over HTTPS. This does not certify connectivity from the user's Windows terminal.
