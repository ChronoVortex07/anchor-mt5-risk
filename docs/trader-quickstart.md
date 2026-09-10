# Connect Telegram to your MetaTrader 5 account

You need a Windows MT5 desktop terminal with a **demo hedging account** and an Anchor service operator's **Telegram bot link + HTTPS API URL**. MT5 on mobile cannot host an Expert Advisor. The terminal must remain running for remote commands to work.

This prerelease provides source code. Its EA has **not yet been compiled or demo-broker validated by the publisher**. Compile and test locally before enabling execution. There is no universal hosted bot or broker account bundled with the open-source repository.

## 1. Open your operator's Telegram bot

Maintainer bot: [@cv_mt5_bot](https://t.me/cv_mt5_bot). Its service address is `https://mt5.chronovortex.dev`. The Telegram webhook is configured. Open the bot and send `/link` to begin pairing.

Open the exact `https://t.me/<bot_username>` link supplied by your operator. Press **Start**, then send:

```text
/link
```

The bot replies with a one-use pairing code, valid for ten minutes, the HTTPS API URL, and download/setup links. Keep the code private. You never need to give the bot your broker login password, Telegram password, or Telegram login code. If you do not have an operator, [host your own service](telegram-setup.md) first.

## 2. Download the Expert Advisor

- [Download the EA source ZIP](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.1.0-alpha.1/anchor-mt5-ea-source.zip).
- [Download SHA256SUMS.txt](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/download/v0.1.0-alpha.1/SHA256SUMS.txt).
- [Read the prerelease notes](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/tag/v0.1.0-alpha.1).

The ZIP includes **all** `.mq5`/`.mqh` sources under `MQL5/Experts/AnchorRisk/`, plus the license and installation/checklist documents. It intentionally contains no `.ex5` executable because compilation has not been verified. Do not download only the main `.mq5` file; its include files are required.

Optional integrity check in PowerShell:

```powershell
Get-FileHash .\anchor-mt5-ea-source.zip -Algorithm SHA256
```

Compare the resulting hash with `SHA256SUMS.txt` from the release. The checksum detects corruption; it is not a substitute for trusting/reviewing the release source.

## 3. Install and compile in MT5

1. Extract the ZIP.
2. In MT5, choose **File → Open Data Folder**.
3. Copy the extracted **MQL5** folder into that data folder, merging its folders. The final main-file path should be:

```text
<Data Folder>\MQL5\Experts\AnchorRisk\BreakEvenAgent.mq5
```

4. Press **F4** to open MetaEditor. Open that file and press **F7** to compile. Inspect the Errors tab. Proceed only after compilation succeeds and warnings have been reviewed. Compilation creates `BreakEvenAgent.ex5` beside the source. [MetaQuotes compilation instructions](https://www.metatrader5.com/en/metaeditor/help/development/compile).
5. Return to MT5. Refresh **Navigator → Expert Advisors**; expand **AnchorRisk**. Drag **BreakEvenAgent** onto one chart. Use only one instance per terminal.

For upgrades, stop the old EA and reconcile any pending operation before replacing files. Never delete `MQL5/Files/RiskAgent/journal.json` merely to retry a command.

## 4. Allow HTTPS and configure the EA

In **Tools → Options → Expert Advisors**, enable **Allow WebRequest for listed URL** and add your operator's origin, for the maintainer service, `https://mt5.chronovortex.dev`. Use the real URL returned by `/link`. See [MT5's official platform settings](https://www.metatrader5.com/en/terminal/help/startworking/settings).

EA Inputs:

| Input | Set it to |
|---|---|
| `ApiUrl` | Operator's HTTPS origin; no `/v1/agent/poll` suffix |
| `PairingCode` | Fresh code from `/link` |
| `ExecutionEnabled` | **false** during installation and preview testing |
| `BEBufferPoints` | `0` for entry price; positive broker points for a local BE+ estimate |
| `MaxDeviationPoints` | Your tested maximum close deviation in broker points; default `20` |

Keep your broker's MT5 login/server unchanged after pairing. The EA connects to the backend by outbound HTTPS polling; you do not need to open a port on your PC. Check the **Experts** tab for pairing/heartbeat messages. If the pairing code expired, request another with `/link`.

## 5. Select account and map symbols

Open the operator's dashboard URL and sign in with the **same Telegram account**. Confirm the broker/server and last four account digits are correct. Select that account. Under **Edit aliases**, map `gold` to the exact symbol displayed in MT5 Market Watch, including suffixes (for example `XAUUSD.a`). The service never guesses broker suffixes.

If you have multiple accounts, select the intended account on the dashboard or use the account-selection buttons returned by `/link`. Each account needs its own terminal/paired agent. Use dashboard **Revoke** to disconnect an installation; unresolved executions must be reconciled before re-pairing.

## 6. Try previews

```text
/be gold 50
/close gold 50
```

- `/be`: protect approximately the requested percentage **by lot volume**, counting already-protected positions. Whole-ticket protection may overshoot. It never closes tickets to meet a BE percentage.
- `/close`: reduce that percentage of **gross** lot volume, worst-cost layers first. The final ticket may be partially closed and rounded down to valid lot increments.
- Omit the percentage to request 100%, for example `/be gold` or `/close gold`.
- If BUY and SELL positions coexist, BE requires `/be gold buy 50` or `/be gold sell 50`. Close defaults to both directions.

Each request produces a live preview and **Confirm / Cancel** buttons. Previews expire quickly. Review the exact symbol, directions, gross volume and planned volume. Confirmation recalculates live state; it does not blindly reuse old tickets. With `ExecutionEnabled=false`, execution is rejected even after confirmation.

## 7. Enable execution only for deliberate demo validation

Complete the [demo checklist](demo-checklist.md), including failure/restart scenarios. To begin its demo execution tests, enable MT5's **Algo Trading**, permit algorithmic trading for this EA, and explicitly change `ExecutionEnabled=true` in its Inputs. Broker/account/EA permissions must all allow trading. No Telegram command can toggle this setting.

BE+ is a stop-price buffer estimate, not a guarantee of a non-negative fill. Fees, swaps, gaps and slippage still matter. Closing one side of a hedge can increase net directional exposure even when gross lots decrease. Read actual broker-confirmed results; an attempted modification is not proof of protection.

For offline, mismatch or uncertain-result errors, follow your operator's instructions and [the runbook](operations-runbook.md). Do not blindly resend `/close` after a timeout.
