# Anchor Local Risk Panel

The local panel is a separate, native MT5 version of Anchor. It reuses the
position planner and narrow broker executor, but has no Telegram, backend,
database, pairing, web login or network dependency. The existing remote service
and `BreakEvenAgent` remain unchanged.

## What it looks like

Attach `LocalRiskPanel` to a chart and it creates a dark panel in the chart's
upper-left corner. It displays the exact chart symbol, masked account number,
BUY/SELL exposure and the volume already protected at the configured break-even
level.

Choose 25%, 50% or 100%, then select one of these actions:

- **BE / BUY** or **BE / SELL** moves eligible stops toward entry plus the
  locally configured point buffer. It never makes an existing stop worse and
  never changes take profit.
- **CLOSE BUY**, **CLOSE SELL** or **CLOSE BOTH** reduces gross lot volume,
  worst price P&L per lot first. A final ticket can be partially closed subject
  to the broker's volume rules.

The first click only creates a preview. The preview shows target, planned,
already-protected and gross volume. A separate confirmation expires after 15
seconds by default. Confirmation rereads and replans live positions before any
broker request.

## Install

1. Use a Windows MT5 terminal logged into a **demo hedging account**.
2. Choose **File → Open Data Folder** in MT5.
3. Copy the ZIP's `MQL5` directory into the data folder.
4. Open `MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5` in MetaEditor and press
   **F7**. Resolve every compiler error and inspect warnings.
5. In MT5, refresh **Navigator → Expert Advisors**, then attach
   **AnchorLocal → LocalRiskPanel** to the chart for the exact symbol to manage.

No URL or WebRequest permission is required.

## Inputs and safety gates

| Input | Meaning |
|---|---|
| `ExecutionEnabled` | Defaults to `false`; previews work, confirmation does not trade. |
| `AllowLiveAccount` | Defaults to `false`; separately blocks real-money accounts. |
| `BEBufferPoints` | `0` means entry; a positive value moves the requested stop beyond entry by broker points. |
| `MaxDeviationPoints` | Maximum close deviation in broker points. |
| `ConfirmationSeconds` | Preview validity, from 5 to 60 seconds. |
| `PanelX`, `PanelY` | Panel offset from the chart's upper-left corner. |

Execution also requires MT5 Algo Trading, terminal permission, account
permission and per-EA trading permission. The panel only supports hedging-mode
accounts.

## Demo checks before live use

- Compile with zero errors and review all warnings.
- With `ExecutionEnabled=false`, exercise every preview and verify there are no
  broker requests.
- Verify BUY and SELL BE behavior, an already-better stop, TP preservation,
  broker stop/freeze levels, and a mixed-side account.
- Verify 25%, 50% and 100% closes, including partial volume, minimum/step rules,
  FOK/IOC behavior and the ticket order against broker history.
- Change or manually close a position after preview and before confirmation;
  confirm the panel replans instead of reusing the old preview.
- Let a preview expire and confirm it cannot execute.
- Disable Algo Trading and confirm execution fails closed.
- Restart and change accounts; confirm the old panel cannot execute on the new
  account without being reattached.
- Reconcile any `UNCERTAIN` outcome against broker history before clicking
  another close action.

Only after those checks pass on the intended broker should you consider setting
both `ExecutionEnabled=true` and `AllowLiveAccount=true` on a real account.
Stops can gap or slip, and fees/swaps may make entry-price protection a net loss.
Closing one side of a hedge can increase net directional exposure.
