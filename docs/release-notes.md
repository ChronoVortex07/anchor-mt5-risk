# Anchor v0.2.0-alpha.1 — local MT5 panel

This prerelease adds a separate native MT5 interface for traders who do not
need remote Telegram control. The existing `BreakEvenAgent`, Telegram service,
dashboard and v0.1 release remain unchanged.

## Download

Download both release assets:

- `anchor-local-risk-panel-source.zip`
- `anchor-local-risk-panel-SHA256SUMS.txt`

The ZIP is source-only. Extract its `MQL5` directory into the MT5 data folder,
compile `MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5` in MetaEditor, and attach
it to a demo hedging-account chart. Follow the complete
[local panel installation guide](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/v0.2.0-alpha.1/docs/local-panel.md).

## Panel controls

- Exact current-chart symbol; no symbol mappings or suffix guessing
- Live BUY/SELL and configured-BE exposure summary
- 25%, 50% and 100% volume targets
- BE protection for BUY or SELL positions
- Worst-cost-first close for BUY, SELL or both sides
- Expiring preview and explicit confirmation
- Automatic refreshed preview and second confirmation if the plan changes
- Ticket-level preview/result logging in MT5's Experts log

The local EA makes no network requests and requires no Telegram bot, server,
database, credentials, pairing or WebRequest permission.

## Safety defaults

`ExecutionEnabled=false` provides previews without broker mutation.
`AllowLiveAccount=false` independently blocks real-money execution. Demo
execution still requires enabling Algo Trading and all normal MT5 permissions.
Netting accounts remain unsupported.

## Validation status

Repository CI validates packaging, shared planner fixtures, the Python reference
model and the unaffected web service. The publisher's Linux environment cannot
run MetaEditor or connect the EA to an MT5 broker. This release therefore does
not claim MQL5 compilation, broker compatibility or live-trading readiness.
Compile it and complete the documented demo checks on every intended broker and
device before considering live use.
