# Install the Anchor Local Risk Panel

The local panel runs entirely inside a Windows MetaTrader 5 terminal. It does
not need Telegram, a web server, PostgreSQL, an API URL, a pairing code or
WebRequest permission. It only manages positions for the exact symbol of the
chart to which it is attached.

This is a source prerelease. The repository publisher cannot run MetaEditor or
an MT5 broker from the Linux build environment, so you must compile it and test
it on a demo hedging account before considering live use.

## 1. Download the release

Download both files from
[Anchor v0.2.0-alpha.1](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/tag/v0.2.0-alpha.1):

- `anchor-local-risk-panel-source.zip`
- `anchor-local-risk-panel-SHA256SUMS.txt`

Do not download only `LocalRiskPanel.mq5` from the source browser. The EA needs
the included `Include/RiskAgent/*.mqh` files.

Optional integrity check in PowerShell:

```powershell
Get-FileHash .\anchor-local-risk-panel-source.zip -Algorithm SHA256
Get-Content .\anchor-local-risk-panel-SHA256SUMS.txt
```

The two SHA-256 values should match. The checksum detects an incomplete or
altered download; it does not replace source review or demo testing.

## 2. Copy it into MT5

1. Open the Windows MT5 terminal you intend to test.
2. Select **File → Open Data Folder**.
3. Close MetaEditor if it is already open.
4. Extract the downloaded ZIP. It contains a top-level `MQL5` folder.
5. Copy that `MQL5` folder into the MT5 data folder and allow Windows to merge
   the folders. This does not replace the whole existing `MQL5` directory.
6. Confirm the final path is exactly:

```text
<MT5 Data Folder>\MQL5\Experts\AnchorLocal\LocalRiskPanel.mq5
```

The adjacent directory
`MQL5\Experts\AnchorLocal\Include\RiskAgent\` should contain five `.mqh`
files. If the final path contains nested folders such as
`anchor-local-risk-panel-source\MQL5\MQL5`, move the inner `MQL5` contents up
one level.

## 3. Compile it

1. Press **F4** in MT5 to open MetaEditor.
2. In MetaEditor's Navigator, open
   **Experts → AnchorLocal → LocalRiskPanel.mq5**.
3. Press **F7** or select **Build → Compile**.
4. Inspect the Errors panel. Continue only if compilation reports zero errors;
   review every warning.
5. Confirm `LocalRiskPanel.ex5` was created next to the `.mq5` source.

If compilation fails, copy the complete error list, MetaTrader terminal build
number and MetaEditor build number. Do not enable execution while resolving it.

## 4. Attach it in preview-only mode

1. Return to MT5.
2. Open a chart for the exact broker symbol you want to manage, for example
   `XAUUSD` or `XAUUSD.a`. The panel does not guess symbol suffixes.
3. In **Navigator → Expert Advisors**, right-click and select **Refresh**.
4. Drag **AnchorLocal → LocalRiskPanel** onto the chart.
5. On the **Inputs** tab, keep:

```text
ExecutionEnabled = false
AllowLiveAccount = false
BEBufferPoints = 0
MaxDeviationPoints = 20
ConfirmationSeconds = 15
```

6. Allow the EA to start. A dark panel should appear in the chart's upper-left
   corner. If necessary, adjust `PanelX` and `PanelY` in the EA inputs.

With `ExecutionEnabled=false`, the panel calculates previews but confirmation
cannot send a broker trade request.

## 5. Learn the controls

The header shows the chart symbol, masked account number, execution gate and
current BUY/SELL exposure.

1. Select **25%**, **50%** or **100%** target volume.
2. Select an action:
   - **BE / BUY** or **BE / SELL** plans stop-loss protection at entry plus the
     locally configured buffer.
   - **CLOSE BUY**, **CLOSE SELL** or **CLOSE BOTH** plans a gross-volume
     reduction, worst price P&L per lot first.
3. Read the target, planned, already-protected and gross volumes.
4. Either select **CANCEL** or use the expiring **CONFIRM EXECUTION** button.

Changing the percentage invalidates the old preview. If positions change before
confirmation, the panel displays a refreshed preview and requires another
confirmation instead of silently executing the changed plan. Ticket-level
preview and result details are also written to MT5's **Experts** log.

## 6. Test execution on a demo account

Use a demo account in `RETAIL_HEDGING` margin mode. Netting accounts are
intentionally unsupported.

1. Open small demo positions for the chart symbol.
2. Open the panel's properties and change `ExecutionEnabled=true`.
3. Leave `AllowLiveAccount=false`; this still permits demo execution.
4. Enable MT5's **Algo Trading** button and allow algorithmic trading for the
   EA.
5. Preview a small BE action, confirm it and compare the resulting SL and
   unchanged TP with the preview and Experts log.
6. Preview the smallest practical partial close, confirm it and compare the
   resulting position and exit deal with broker history.
7. Repeat with BUY, SELL, mixed-side, already-protected, invalid stop-distance,
   partial-volume and expired-preview cases.

If the panel reports `UNCERTAIN`, do not repeat the close blindly. Inspect open
positions and broker deal history first.

## 7. Real accounts

Real-account execution requires all of the following:

- `ExecutionEnabled=true`
- `AllowLiveAccount=true`
- MT5 Algo Trading enabled
- Terminal, account and per-EA trading permissions enabled
- A valid, unexpired preview

The two input gates deliberately require editing the EA properties; there is no
panel button that can enable them. Keep both false until the demo checklist has
passed on the intended broker and symbols.

## Inputs

| Input | Meaning |
|---|---|
| `ExecutionEnabled` | Master local execution gate; defaults to preview-only. |
| `AllowLiveAccount` | Separate real-money opt-in; has no effect on demo accounts. |
| `BEBufferPoints` | `0` means entry; positive values request entry plus broker points in the protective direction. |
| `MaxDeviationPoints` | Maximum close deviation in broker points. |
| `ConfirmationSeconds` | Preview validity from 5 to 60 seconds. |
| `PanelX`, `PanelY` | Pixel offset from the chart's upper-left corner. |

## Common messages

| Message | Meaning / next step |
|---|---|
| `PREVIEW ONLY` | Set `ExecutionEnabled=true` only when ready for demo execution. |
| `LIVE ACCOUNT LOCKED` | The account is real and `AllowLiveAccount` remains false. |
| `NOT_HEDGING` | The account uses an unsupported netting mode. |
| `NO_POSITIONS` | No matching positions exist for the exact chart symbol and selected side. |
| `SYMBOL_NOT_FOUND_OR_STALE` | Confirm the chart symbol is tradable, selected and receiving current ticks. |
| `NO_ELIGIBLE_POSITIONS` | Nothing can be changed under the target, stop/freeze or volume constraints. |
| `EA_TRADING_DISABLED` | Enable terminal Algo Trading and the EA's trading permission. |
| `Positions changed; review refreshed preview` | Review the new plan and confirm again. |
| `UNCERTAIN` | Reconcile against open positions and broker history before another action. |

## Testing on several devices

Repeat the download and compilation steps in each MT5 terminal's own data
folder. Settings and compiled files are local to that terminal; there is no
account pairing or cloud synchronization. Record these details with any issue:

- Windows version and display scaling
- MT5 and MetaEditor build numbers
- Broker and server name
- Exact symbol and account margin mode
- Compile errors/warnings
- Screenshot of the panel
- Relevant Experts log lines, with account numbers obscured

Avoid running two local panels for the same symbol in one terminal while testing
execution. The EA never sends broker passwords or data outside MT5.

Stops can gap or slip, and commission, swap or fees can make entry-price
protection a net loss. Closing one side of a hedge can increase net directional
exposure.
