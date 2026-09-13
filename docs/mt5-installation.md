# MT5 installation and compilation

For the ready-to-extract ZIP and beginner steps, see [the trader quickstart](trader-quickstart.md) and [download the source prerelease](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/tag/v0.1.0-alpha.2).

Use a Windows MT5 terminal logged into a **demo hedging account**. Linux hosts the backend; the EA runs inside the user's own MT5. Never enter broker credentials in this service.

1. In MT5 choose **File → Open Data Folder**.
2. Copy the entire repository `mt5` directory to `MQL5/Experts/AnchorRisk/`, preserving `Include/RiskAgent/` and `tests/` relative paths.
3. Open `Experts/AnchorRisk/BreakEvenAgent.mq5` in MetaEditor and press **F7**. Resolve all errors and inspect all warnings before attaching it. Record compiler/terminal build numbers and the compile log.
4. Compile `tests/PlannerTests.mq5`. It is a script (OnStart); copy its output to `MQL5/Scripts` or execute via MetaEditor/terminal as a script on a demo chart. Alternatively copy the `tests` folder under Scripts together with its relative Include path. It performs pure tests and sends no broker requests.
5. Add the exact HTTPS API origin to **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**. Confirm the TLS certificate is publicly trusted.
6. Attach **one** RiskAgent instance to a chart in this terminal. The chart symbol does not limit command targets; every command identifies its exact symbol and scans hedging positions across the account.
7. Set `ApiUrl` to your HTTPS origin (no trailing path recommended), `PairingCode` to the code from `/link`, **ExecutionEnabled=false**, `BEBufferPoints=0`, `MaxDeviationPoints=20` initially.
8. Check Experts logs for successful pairing/heartbeat; confirm account suffix/server/mode in the dashboard. Map gold explicitly to the actual broker symbol.
9. Complete the demo checklist before setting `ExecutionEnabled=true`. This is a deliberate local opt-in. No backend request can enable it.

Optional command-line compilation on Windows (adjust paths):

```powershell
& 'C:\Program Files\MetaTrader 5\metaeditor64.exe' /compile:'C:\path\MQL5\Experts\AnchorRisk\BreakEvenAgent.mq5' /log:'C:\temp\anchor-compile.log'
& 'C:\Program Files\MetaTrader 5\metaeditor64.exe' /compile:'C:\path\MQL5\Experts\AnchorRisk\tests\PlannerTests.mq5' /log:'C:\temp\anchor-tests-compile.log'
```

Read the log and confirm an `.ex5` was produced; process exit alone is not compilation evidence. The current delivery has no MetaEditor or broker execution evidence. Network tests must use a running terminal: [MetaQuotes documents that WebRequest is unavailable in Strategy Tester](https://www.mql5.com/en/docs/network/webrequest).

## Local files

The EA uses `MQL5/Files/RiskAgent/` (terminal-local, **not** FILE_COMMON):

- `credentials.json`: public agent ID, secret, installation ID, bound account/server/API/path. The secret is plaintext locally because it must authenticate polls; protect the Windows user profile.
- `installation.txt`: installation UUID.
- `journal.json`: STARTED execution marker or exact DONE result; never delete it during an unresolved operation.
- `recent.txt`: last 128 acknowledged command IDs.
- `instance.lock`: exclusive handle to prevent duplicate chart instances.

`FileFlush` and verified file replacement are used before sending to the broker, but MT5 files and broker execution cannot form one atomic transaction. Corruption or an incomplete journal blocks execution; investigate rather than deleting files to retry.

## Re-pairing

Revoke the agent in the dashboard. If an execution was already delivered, first reconcile its outcome; revocation does not undo a broker request already in flight. After checking no unresolved execution remains, remove the EA, archive its files securely, remove the credential/installation files, obtain a new `/link` code and attach again. Preserve journal/history as incident evidence. Re-pairing retains account ownership and symbol mappings. An account identity mismatch is latched; returning to the old login alone does not resume commands.

The API generates the authentication secret. The EA-generated UUID is only a collision-resistant installation/session identifier, not a substitute for the secret. Each initialization uses a new session ID. A newly started instance waits for the old heartbeat to age out (10 seconds); it may submit its recovered result, but cannot replay a leased execution from the old session.

## Broker limitations

Hedging only. At most 128 matching symbol positions per plan. Quote freshness uses MT5 server time and requires a recent quote. Close supports FOK/IOC; symbols requiring another fill mode fail closed. A position larger than the broker's maximum per-deal volume may only be partially reduced in one command. BE normalizes to tick size in the protective direction, respects stop/freeze distances, preserves TP, checks broker retcode and re-reads the final position. Close requires a broker exit-deal record; delayed deal visibility is classified UNCERTAIN. Commission/swap are not included in the price-buffer estimate.

## Connection troubleshooting

`Pairing failed. HTTP -1` means MT5 did not receive an HTTP response. It does not mean the server rejected the pairing code. EA version 0.11 reports `WEBREQUEST_FAILED` with MT5's numeric error; share that line without credentials.

1. Set **ApiUrl** in EA Inputs to the origin supplied by `/link`. For the maintainer bot this is **https://mt5.chronovortex.dev**. The source's `api.example.com` placeholder is not a working service.
2. Add the same origin to **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**, with the checkbox enabled. The Inputs setting and terminal permission are both required.
3. Attach directly to a chart in a logged-in demo terminal. Network requests do not work in Strategy Tester.
4. Verify the origin's `/healthz` URL from the same Windows computer. A browser success alone does not verify MT5 permissions or rule out an interactive Cloudflare challenge.
5. Obtain a fresh `/link` code after fixing the settings. If the first request may have succeeded but lost its response, check the account in the dashboard before re-pairing. Never delete an unresolved execution journal.

| Diagnostic | Meaning / next check |
|---|---|
| MQL 4014 | Function not permitted: check WebRequest allowlist and runtime context |
| MQL 5200 | Invalid URL: check ApiUrl |
| MQL 5201 | Connection failed: check Internet, DNS, proxy and TLS |
| MQL 5202 | Timeout: pairing may have reached the server; inspect account state |
| HTTP 401 + INVALID_PAIRING_CODE | Server rejected an expired, used or incorrect pairing code |
| HTTP 422 | Request format rejected; check full code and logged-in MT5 account |
| HTTP redirect or 403 | Operator should inspect Cloudflare Access/challenge settings |

See [MetaQuotes WebRequest error documentation](https://www.mql5.com/en/book/advanced/network/network_http). Pairing uses a bounded five-second timeout; regular polling retains its two-second timeout. Errors never log credentials or full response bodies.

Dashboard **Bot domain invalid** is a separate Telegram widget setting. The bot owner should open the BotFather mini app → matching bot → Login Widget → Allowed URLs, register the HTTPS origin (for the maintainer: `https://mt5.chronovortex.dev`) and root redirect, then reload the site. If rejection persists, the operator must verify legacy-widget compatibility. It cannot be fixed with an EA pairing code.
