# Repository audit and implementation plan

Audit: 2026-09-10. The initial environment was a shared deployment workspace with no MT5 application checkout. Inspected repository inventory, development conventions, Compose templates and the existing Caddy gateway documentation. Created an isolated greenfield project and preserved unrelated infrastructure.

Reuse: Docker Compose conventions (isolated projects/volumes, non-root app, health checks, log rotation); existing Caddy edge gateway integration. Do not alter existing stacks. Standalone VPS deployment uses Caddy for automatic HTTPS as well.

Explicit prompt overrides: exactly three Telegram commands (`/link`, `/be`, `/close`). Close is an explicitly authorized addition to the original BE-only protocol. It can only reduce existing hedging positions by exact symbol and fraction; no remote ticket, order side, price, TP or order-entry interface. `/be <identifier>` defaults to 100%. `/close <identifier>` defaults to 100%, always previewed. Account selection, alias mapping, status and revocation use inline buttons/dashboard.

Confirmed close semantics: gross lot volume across both directions; lowest unrealized price profit per lot first (BUY highest entry, SELL lowest entry). Partial final ticket permitted. Round down to broker volume step, never exceed requested volume; report underfill/minimum-lot constraints. Reducing gross exposure may increase directional net exposure when closing one leg of a hedge. Preview discloses direction breakdown; no claim that closing guarantees lower portfolio risk.

Milestones:
1. Normalized PostgreSQL schema/migration, pairing/auth/binding, durable queue, transaction/ownership tests and fake EA.
2. Deterministic Decimal reference planner, MQL5 pure planner/validator and network/persistence integration.
3. Narrow SLTP and position-bound close executor, fail-closed crash journal, demo validation checklist (actual MT5 unavailable on Linux).
4. Three Telegram commands, durable webhook deduplication/outbox, inline account selection and preview/confirm/cancel.
5. Read-only status plus mapping/revoke dashboard authenticated with Telegram login, Compose, backups and operational/threat documentation.

Safety decision: leased commands are never reassigned to a new execution. Retries redeliver the same ID within its original deadline. After an unacknowledged execution expires, the account is BLOCKED_UNCERTAIN until a matching result arrives. A restart with an incomplete local execution journal returns UNCERTAIN and retains the server block; re-pairing does not clear it. Explicit operator reconciliation is required.
