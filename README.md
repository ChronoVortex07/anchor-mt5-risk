# Anchor — MT5 risk controls

[![CI](https://github.com/ChronoVortex07/anchor-mt5-risk/actions/workflows/checks.yml/badge.svg)](https://github.com/ChronoVortex07/anchor-mt5-risk/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A native local MT5 panel and an optional Telegram/FastAPI service for reducing
existing hedging-account exposure. Broker credentials remain exclusively in
MT5.

**Status:** source prerelease. The supporting Python/browser checks pass, but
the MQL5 sources have not been compiled or executed against MT5 in this Linux
environment. Keep either EA in preview mode until its demo validation checklist
passes. This is not a live-trading readiness sign-off.

## Choose a version

- **Local MT5 panel:** no server or Telegram required. [Setup guide](docs/local-panel.md) · [source ZIP](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.2.0-alpha.1/anchor-local-risk-panel-source.zip) · [checksum](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.2.0-alpha.1/anchor-local-risk-panel-SHA256SUMS.txt)
- **Remote Telegram version:** [trader setup](docs/trader-quickstart.md) · [source ZIP](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.1.0-alpha.2/anchor-mt5-ea-source.zip) · [checksum](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.1.0-alpha.2/SHA256SUMS.txt)
- **Service operators:** [Telegram/backend deployment guide](docs/telegram-setup.md).

Maintainer bot: [@cv_mt5_bot](https://t.me/cv_mt5_bot). Its webhook is configured at [mt5.chronovortex.dev](https://mt5.chronovortex.dev). Open the bot and send `/link` to begin demo-account setup.

There is no universal hosted deployment bundled with this repository. Get the actual `https://t.me/<bot_username>` and HTTPS API URL from your operator, or create your own using the setup guide. The registration utility prints your real bot link after verifying its identity. The ZIP contains all EA sources and includes, **not** an unverified precompiled EX5.

## Three Telegram commands

| Command | Meaning |
|---|---|
| `/link` | Create a one-use pairing code; show account-selection buttons |
| `/be gold 50` | Preview protecting at least approximately 50% of position volume with entry/locally configured BE+ stops |
| `/close gold 50` | Preview closing 50% of gross lot volume, worst-cost lots first |

Omitted percentage means **100%**. `all` also means 100%. Percentages must satisfy `0 < pct <= 100`. Both risk actions require an expiring **Confirm / Cancel** preview. `/be gold buy 50` and `/be gold sell 50` resolve mixed-side ambiguity. `/close` defaults to both directions; explicit `buy` / `sell` is supported too.

“Worst cost” is lowest unrealized **price P&L per lot**: highest BUY entries, lowest SELL entries; compare Bid-entry for BUY with entry-Ask for SELL. It excludes accrued commission/swap. A partial final close is rounded down to the broker's volume step; minimum lot/residual constraints may underfill. Gross exposure is BUY lots + SELL lots, **not net lots**. Closing one hedge leg can increase net directional exposure.

`gold` must be mapped to an exact broker symbol in the account dashboard. Without a mapping, identifiers are treated literally: no fuzzy matching, suffix guessing or default gold substitution. BE protects whole tickets, counts existing protection, and may overshoot a target because positions differ in size. It never closes a ticket merely to hit the BE percentage. BE+ is a stop-price buffer estimate, not a guarantee of a non-negative fill.

## Local-only panel alternative

[`LocalRiskPanel.mq5`](mt5/LocalRiskPanel.mq5) is a native MT5 panel for traders
who do not need remote Telegram control. It operates on the exact current chart
symbol and reuses the same planner/executor, while requiring no backend,
database, account pairing, dashboard or WebRequest permission.

[Download v0.2.0-alpha.1](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/tag/v0.2.0-alpha.1)
and follow the [local panel setup guide](docs/local-panel.md). The remote service
and `BreakEvenAgent` remain available and unchanged. Developers can reproduce
the ZIP with `python tools/package_local_panel.py --output build`.

## Start on Linux

Prerequisites: Docker Engine and Compose v2.24.4+ (overlay reset support).

```bash
cp .env.example .env
chmod 600 .env
# Set POSTGRES_PASSWORD to random URL-safe hex; fill Telegram fields when ready.
docker compose --env-file .env -f infra/compose.yaml up -d --build --wait
curl http://127.0.0.1:18089/readyz
```

Dashboard: `http://127.0.0.1:18089`. The default development stack is loopback-only and uses its own database volume. The dashboard sign-in and real EA require HTTPS; see [deployment](docs/deployment.md). No bot token is needed for health checks or simulator integration tests. An unconfigured dashboard displays onboarding.

Keep `.env`, agent credentials, pairing codes and local execution journals private. Deployment configuration is separate from the public source repository.

## Pair an MT5 demo account

1. Follow [Telegram service setup](docs/telegram-setup.md); run `python -m tools.register_webhook --drop-pending-updates` inside the backend image after setting its environment. Configure the website URL in the BotFather mini app → your bot → Login Widget → Allowed URLs; see the setup guide.
2. Send `/link` in a **private** Telegram conversation. Code format: `XXXX-XXXX-XXXX`, expires in 10 minutes.
3. Install [BreakEvenAgent.mq5](mt5/BreakEvenAgent.mq5) with its includes. Set `ApiUrl`, `PairingCode`, `ExecutionEnabled=false`, and allow the HTTPS URL in MT5 WebRequest settings.
4. Sign into the dashboard using the same Telegram identity. Add `gold → your exact broker symbol`. Choose an account via dashboard or `/link` inline buttons.
5. Request `/be gold 50` and inspect the preview. Execution remains disabled until explicitly enabled locally in the EA.

[MT5 installation and compile instructions](docs/mt5-installation.md) · [Demo test checklist](docs/demo-checklist.md)

## Tests and simulator

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
.venv/bin/pytest backend/tests
.venv/bin/ruff check --config backend/pyproject.toml backend tools
.venv/bin/ruff format --check --config backend/pyproject.toml backend tools
npm ci --prefix frontend
npm run build --prefix frontend
```

SQLite is only the quick test fallback. Run the concurrency suite against a **dedicated disposable PostgreSQL database named `risk_test`**:

```bash
TEST_DATABASE_URL=postgresql+psycopg://risk:test-only@127.0.0.1:55439/risk_test \
  .venv/bin/pytest backend/tests
```

Tests reset that database's application tables. Never point this setting at a real account database. [Testing guide](docs/testing.md) describes migrations, browser checks, and broker limitations.

A standalone simulator can pair using a Telegram-created code:

```bash
.venv/bin/python tools/fake_agent.py --url http://127.0.0.1:18089 \
  --pairing-code XXXX-XXXX-XXXX --execute-simulation
```

The fake agent never reaches a broker. `--failure reject` / `--failure uncertain` exercise failure paths. Its synthetic positions and recent execution cache reset on restart; it is a protocol-testing tool, not a substitute for the real EA's persistent journal.

## Architecture and operations

- [Audit and implementation plan](docs/implementation-plan.md)
- [Architecture](docs/architecture.md) and [agent protocol](docs/agent-protocol.md)
- [Threat model](docs/threat-model.md) and [remaining risks](docs/remaining-risks.md)
- [Deployment](docs/deployment.md), [runbook](docs/operations-runbook.md), [backup and restore](docs/backup-restore.md)
- [Validation report](docs/validation-report.md)

No order entry, pending-order placement, generic broker action API, remote TP edits, broker password storage, subscriptions, Redis or distributed task queue is implemented.

## Open source

Released under the [MIT License](LICENSE). See [contributing](CONTRIBUTING.md), [security reporting](SECURITY.md) and [changelog](CHANGELOG.md). Build the deterministic EA source archive with `python tools/package_ea.py --output build`.
