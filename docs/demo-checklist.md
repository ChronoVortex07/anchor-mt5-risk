# Demo-account release gate

All boxes below are **not yet performed on MT5**. Use a demo hedging account, record broker/server, terminal/compiler version, exact symbols and contract metadata. Preserve compile logs, request/result IDs, Experts logs, screenshots of SL/TP, and broker deal history. Do not use a live account to establish correctness.

## Compile and pairing

- [ ] Compile EA and PlannerTests in MetaEditor with zero errors; review warnings.
- [ ] Run PlannerTests: tick rounding, BUY/SELL monotonicity, volume/overshoot, existing protection, mixed sides, worst-cost partial close, JSON rejection.
- [ ] Pair from private Telegram `/link`; verify one-time code consumption and expiry.
- [ ] Restart MT5: saved credential and identity still work, no duplicate EA instance accepted.
- [ ] Copy credential into a different terminal data path: reject; concurrent session gets AGENT_SESSION_BUSY.
- [ ] Switch login/server: no command delivered/executed; mismatch remains latched after switching back.
- [ ] Verify netting account refuses both layered operations.

## Preview mode (`ExecutionEnabled=false`)

- [ ] Pair/poll/dashboard and `/be` / `/close` previews work with execution off.
- [ ] Confirm is rejected while execution is disabled; no OrderSend call occurs.
- [ ] Literal exact symbol and account-specific `gold` mapping select the same intended symbol.
- [ ] Unknown symbol fails; suffix ambiguity is never guessed.
- [ ] Mixed BUY/SELL BE returns AMBIGUOUS_SIDE; explicit side resolves.
- [ ] Omitted percentage and `all` mean 100%; invalid/negative/zero/nonfinite percentages fail.
- [ ] Preview shows gross BUY/SELL lots and requested/planned volumes.
- [ ] Expired/cancelled/cross-user confirmation never creates execution.

## BE demo execution (deliberate local opt-in)

- [ ] Equal-volume BUY layers, unequal volumes, SELL layers and no-SL tickets.
- [ ] Existing stops already at/beyond BE count; a better SL is unchanged.
- [ ] Whole-ticket overshoot is reported; no close is generated for BE.
- [ ] ENTRY (buffer 0) and positive local BE+ points normalize to valid tick size, including non-decimal tick sizes such as 0.25.
- [ ] TP is bit-for-bit unchanged by the submitted SLTP request, including TP=0.
- [ ] Stop level, freeze level, stale quote, market closure and disabled permissions reject safely.
- [ ] Change SL/TP/volume or close a ticket between preview and confirmation: recompute.
- [ ] Change a ticket immediately before send: abort/revalidate; record unavoidable broker race boundaries.
- [ ] Compare every successful result with the actual final broker SL; retcode rejection is not success.

## Close demo execution

- [ ] BUY highest entry first; SELL lowest entry first; mixed side compares price P&L per lot using Bid/Ask.
- [ ] Gross volume target (sum of both sides) rather than ticket count/net exposure.
- [ ] Partial final ticket; floor to volume step; do not exceed requested volume or leave invalid subminimum residual.
- [ ] FOK and IOC behavior including partial fills, different filling modes rejected safely.
- [ ] Returned exit deal matches position identifier, symbol, direction and volume; delayed evidence yields UNCERTAIN.
- [ ] Manual close/disappearance between reads cannot open a reverse position; ticket-bound broker rejection confirmed.
- [ ] Existing SL and TP of residual positions remain unchanged where broker supports partial close.
- [ ] Closing one hedge leg's effect on net exposure is understood; user preview disclosure is visible.

## Fault/restart matrix

- [ ] Duplicate polls/deliveries and confirmation taps: same ID, no duplicate fractional close.
- [ ] Drop HTTP response after broker success: result resubmits; no re-execution.
- [ ] Kill EA/terminal immediately before/after OrderSend: STARTED becomes UNCERTAIN after restart.
- [ ] Kill backend while command leased: original TTL stays fixed, no fresh lease/second command.
- [ ] Leave EA offline beyond TTL and overnight: no stale execution.
- [ ] Broker timeout/placed result/connection loss: stop remaining sends and block account.
- [ ] Revoke during a leased operation: no new polls accepted; already delivered work is reconciled.
- [ ] Backend restore from backup does not cause old trade replay; journal and account block are respected.
- [ ] Run operator reconciliation only with documented broker history; verify auditable unblock.
- [ ] Verify requested, planned and broker-confirmed numbers against broker history for partial outcomes.

Release decision: record evidence for every item and resolve all mismatches before considering live use. A passing Python simulator cannot certify MQL5 compilation or a broker's trade semantics.
