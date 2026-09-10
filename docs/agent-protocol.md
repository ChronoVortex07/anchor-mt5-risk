# Agent protocol v1

Transport: HTTPS only for real EAs. UTF-8 JSON, 64 KiB request/response maximum, unknown input fields rejected. The backend has no generic command creation endpoint accessible to agents. OpenAPI schema is available at `/openapi.json`; interactive documentation is disabled.

## Pair

`POST /v1/agent/pair`, no authentication header:

```json
{"protocol_version":1,"session_id":"15bb825c-a1c4-440e-b2c4-e0c19aac1242","pairing_code":"X7Q9-KF2P-8RWA","installation_id":"82e09d80-d3a0-4dd2-a341-9564d7cb0d19","ea_version":"0.10","account":{"login":12345678,"server":"Broker-Demo","margin_mode":"RETAIL_HEDGING","trade_allowed":true,"expert_trade_allowed":true}}
```

The response contains `agent_id`, `agent_secret`, `protocol_version`. The code is 12 random symbols (~60 bits), belongs to one human, expires in ten minutes, is hashed in the pairing table, and is consumed atomically. The code temporarily exists in an encrypted outbox record for Telegram delivery (key derived from the external bot secret). Pairing is limited to ten attempts/IP/ten minutes, and five issued codes/user/ten minutes. Reverse-proxy client address handling must be trusted.

The agent secret is 32 CSPRNG bytes encoded as 43 base64url characters. Only SHA-256 digest is stored server-side. Pairing response loss deliberately requires revocation/new code rather than a retrievable plaintext secret. Existing active installations must be revoked before re-pairing. An existing account cannot be paired by a different human. A blocked uncertain account cannot be re-paired.

## Poll and result submission

`POST /v1/agent/poll`

```text
Authorization: Bearer <agent_secret>
X-Agent-ID: <agent_uuid>
```

```json
{"protocol_version":1,"session_id":"15bb825c-a1c4-440e-b2c4-e0c19aac1242","installation_id":"82e09d80-d3a0-4dd2-a341-9564d7cb0d19","ea_version":"0.10","account":{"login":12345678,"server":"Broker-Demo","margin_mode":"RETAIL_HEDGING","trade_allowed":true,"expert_trade_allowed":true},"terminal":{"connected":true},"execution_enabled":false,"result":null}
```

Each EA start generates a fresh `session_id` UUID. The current session has a ten-second heartbeat exclusion window. A different session may recover results after that window, but cannot inherit a leased execution; this blocks the account as uncertain.

Every valid poll checks login/server/installation, records heartbeat and small runtime state, optionally acknowledges a result, and returns at most one command. No position snapshot is required at idle. One-second polling with jitter; rate cap 180/agent/minute plus 600/source/minute. The source cap may need operator adjustment for many legitimate terminals behind one NAT. The supplied EA uses a two-second WebRequest timeout and exponential backoff capped at 30 seconds with jitter.

```json
{"protocol_version":1,"server_time":"2026-09-10T12:00:00Z","poll_after_ms":1210,"ack_result_id":null,"code":"OK","command":{"id":"642cedd6-55ed-44aa-9a36-e33aebc9bd9d","type":"PREVIEW_PROTECT_BREAKEVEN","expires_in_ms":25000,"symbol":"XAUUSD.a","side":"AUTO","target_fraction":0.5}}
```

Command fields are **exactly** `id`, `type`, `expires_in_ms`, `symbol`, `side`, `target_fraction`. Allowed types:

| Type | Broker action |
|---|---|
| PREVIEW_PROTECT_BREAKEVEN | None |
| PROTECT_BREAKEVEN | Independently validated, monotonic SLTP change; current TP preserved |
| PREVIEW_REDUCE_EXPOSURE | None |
| REDUCE_EXPOSURE | Capped close of existing hedging tickets only |

Heartbeat replaces a separate PING/REPORT_STATE command in this implementation. No arbitrary prices, remote buffer, ticket targets, entry side, TP, pending order or raw OrderSend payload is accepted. The local buffer is not a remotely tunable stop price. `AUTO` is for BE side inference; `BOTH` is for close. Only exact broker symbols execute.

`expires_in_ms` is computed from the fixed database expiry. The EA measures its deadline using monotonic `GetTickCount64` from **before** the polling request, conservatively accounting for the full round trip. It checks expiry before each send. A wrong local wall clock cannot extend the command. Broker calls themselves may finish after the deadline, but further sends stop.

Results travel in the next poll's `result` field:

```json
{"command_id":"642cedd6-55ed-44aa-9a36-e33aebc9bd9d","status":"PARTIAL","summary":{"code":"OK","symbol":"XAUUSD.a","side":"BUY","total_volume":1.8,"requested_volume":0.9,"already_protected_volume":0.2,"planned_volume":0.7,"confirmed_volume":0.6,"protected_volume":0.8,"buy_volume":1.8,"sell_volume":0,"changed_positions":4,"ineligible_positions":1},"position_results":[{"ticket":"1234","code":"BROKER_REJECTED","volume":0,"retcode":10016,"old_sl":0,"new_sl":0,"tp":2500}]}
```

Statuses: SUCCEEDED, PARTIAL, FAILED, UNCERTAIN. Result schemas bound symbols, ticket strings, volumes, counts and 128 position rows. Machine codes are distinct from the Telegram explanation. Requested, planned, and agent-reported broker-confirmed volume remain separate. A result is accepted only for a command leased to this agent. Duplicate identical results return the same `ack_result_id`; conflicting results get HTTP 409. Expired executions accept late results without redelivery. An agent credential cannot inspect/confirm other accounts or invent commands.

Account mismatches latch `ACCOUNT_MISMATCH`/`REPAIR_REQUIRED` and deliver no command, even after switching back. Uncertain leased executions return `BLOCKED_UNCERTAIN`. A malformed or incompatible protocol gets HTTP 422; invalid/revoked tokens get HTTP 401. The EA logs safe codes, not request bodies or credentials.

## Recovery contract

Keep the persistent journal until the response acknowledges its exact result ID. Duplicate delivery before acknowledgement reuses the cached result, never a fresh percentage calculation. On STARTED recovery, report UNCERTAIN for executions, FAILED for interrupted previews. No automatic retry of a broker send after transport uncertainty. Operator reconciliation requires broker history and current account state; see runbook.
