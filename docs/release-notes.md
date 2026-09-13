# Anchor v0.1.0-alpha.2

Connection diagnostics and dashboard navigation fixes.

- Accounts and Activity now switch dashboard views and show sign-in requirements when signed out.
- Sign-in help explains the BotFather domain setting required by Telegram's login widget.
- EA **0.11** logs the numeric MT5 WebRequest error and known pairing rejection codes, without credentials or raw responses.
- Invalid placeholder/path API URLs fail with instructions. Pairing uses a bounded five-second timeout; normal polling remains two seconds.
- Trade planning, execution permissions and risk restrictions are unchanged.

## Upgrade and connect

Download **anchor-mt5-ea-source.zip** and **SHA256SUMS.txt**. Remove the old EA from its chart, replace the entire `MQL5/Experts/AnchorRisk` source folder with the ZIP contents and compile `BreakEvenAgent.mq5` in MetaEditor. Preserve `MQL5/Files/RiskAgent` credentials and journals; never delete unresolved execution state.

Set `ApiUrl=https://mt5.chronovortex.dev` for [@cv_mt5_bot](https://t.me/cv_mt5_bot), and add that same origin to MT5's enabled WebRequest allowlist. Keep `ExecutionEnabled=false`. For an unpaired terminal, obtain a fresh `/link` code and attach the EA directly to a demo chart.

If pairing reports HTTP -1, share the new `WEBREQUEST_FAILED ... MQL error=...` line without secrets. HTTP -1 is a terminal/request failure, not a server rejection of the code.

For the dashboard's “Bot domain invalid” error, check BotFather mini app → `cv_mt5_bot` → Login Widget → Allowed URLs includes `https://mt5.chronovortex.dev`. If it persists after saving, legacy-widget compatibility needs verification.

**Source only; no EX5 is supplied.** The publisher cannot run MetaEditor or an MT5 demo broker in this environment. Compilation and broker execution remain manual validation requirements.

- [Installation and troubleshooting](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/mt5-installation.md)
- [Demo checklist](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/demo-checklist.md)
