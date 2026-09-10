# Testing

## Automated backend/domain tests

`backend/tests` exercises:

- Pairing entropy format, expiry, single use, token hashing/authentication/revocation and shared rate limits.
- Exact account binding/mismatch latch, account selection/mappings, netting rejection and offline expiry.
- Cross-user inspect/command/confirm/revoke isolation; other agents cannot submit results for an account.
- Pending/leased/confirmation/terminal transitions, cancel/deadlines, dry-run rejection, late identical results, conflicting/unleased results and explicit uncertainty.
- PostgreSQL concurrent command creation, duplicate polls/results and duplicate confirmation; per-session execution fencing.
- Complete private Telegram webhook → encrypted pairing code outbox → fake EA → preview → inline confirmation → execution → result flow, without contacting Telegram or a broker.
- Decimal BE/close volume planning, mixed sides, exact symbol matching, nonfinite percentages, unequal ticket overshoot, stop/freeze levels, tick normalization, TP preservation, already-better stops, disappearing tickets, simulated broker rejection and monotonicity across a grid of states.

Use the root README commands. SQLite fallback is convenient but skips PostgreSQL lock/concurrency tests; it is not a production database. `TEST_DATABASE_URL` must end in `/risk_test`. Tests destroy/recreate application tables there. The dedicated test database must not contain real users or accounts.

## Migrations

On a fresh disposable PostgreSQL database:

```bash
cd backend
DATABASE_URL=<disposable-postgres-url> ../.venv/bin/alembic upgrade head
DATABASE_URL=<disposable-postgres-url> ../.venv/bin/alembic check
# Optional destructive down/up rehearsal ONLY on the disposable database.
DATABASE_URL=<disposable-postgres-url> ../.venv/bin/alembic downgrade base
DATABASE_URL=<disposable-postgres-url> ../.venv/bin/alembic upgrade head
```

Schema migrations are generated as explicit operations, not dynamic imports of current model metadata. The rate-bucket retention migration backfills existing rows before removing its temporary server default.

## Browser tests

```bash
npm ci --prefix frontend
npm run build --prefix frontend
# Start Compose first; install Chromium with `npx playwright install chromium` if needed.
DASHBOARD_URL=http://127.0.0.1:18089 npm test --prefix frontend
```

`CHROMIUM_PATH` optionally selects an existing Chromium binary. Browser tests verify signed-out onboarding and desktop/mobile account/history/revoke/mapping UI. Authenticated account responses are **mock fixtures**; screenshots are not evidence of real broker connectivity. Real Telegram widget sign-in needs configured bot/domain credentials and is a manual integration gate. Backend tests independently verify Telegram login signatures, ownership, session cookies and Origin enforcement.

## MQL5

`mt5/tests/PlannerTests.mq5` runs the original JSON parser and pure `PlanLayers`/stop logic without networking/trading. The Linux environment has neither MetaEditor nor a Windows MT5 terminal; only source review was possible. MQL5 syntax/runtime and actual order behavior are unverified. Use [installation instructions](mt5-installation.md) and the full [demo checklist](demo-checklist.md).

Implementation choices follow primary MetaQuotes documentation: [WebRequest and tester limitation](https://www.mql5.com/en/docs/network/webrequest), [ticket binding in MqlTradeRequest](https://www.mql5.com/en/docs/constants/structures/mqltraderequest), [stop/freeze/tick and filling properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants), [OrderSend return handling](https://www.mql5.com/en/docs/trading/ordersend), [broker return codes](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes), and [sandbox file replacement](https://www.mql5.com/en/docs/files/filemove). These sources define API behavior; reading them does not prove this EA compiles or is broker-certified.

## Remaining validation gates

Actual Telegram webhook delivery/button interaction/login widget; MetaEditor compile; all broker execution and restart/fault scenarios; offsite backup credentials/retention/restore; public TLS/ingress and firewall validation. Backend and browser tests do not cover those external systems.
