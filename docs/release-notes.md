# Anchor v0.1.0-alpha.1

Initial MIT-licensed source prerelease for Telegram-controlled MT5 risk reduction.

- `/link`: pair your own MT5 agent without sharing broker passwords.
- `/be`: preview and confirm volume-based breakeven protection.
- `/close`: preview and confirm gross-volume reduction, worst-cost lots first.
- PostgreSQL command durability, account/session binding, audit and fake-agent tests.
- Docker deployment, React dashboard, Telegram setup utility and operations documentation.

## Downloads

Download **anchor-mt5-ea-source.zip** and **SHA256SUMS.txt** below. Extract the ZIP's MQL5 folder into your MT5 Data Folder; it contains the main EA and all includes. Follow README.txt inside the ZIP.

**This is source, not a precompiled EX5.** MetaEditor compilation and demo-broker execution have not been verified by the publisher. Execution defaults off. Complete the documented demo validation before any live use.

- [Trader setup](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/trader-quickstart.md)
- [Host the Telegram service](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/telegram-setup.md)
- [Demo checklist](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/demo-checklist.md)
- [Remaining risks](https://github.com/ChronoVortex07/anchor-mt5-risk/blob/main/docs/remaining-risks.md)

The maintainer bot is [@cv_mt5_bot](https://t.me/cv_mt5_bot). Its public webhook requires HTTPS deployment; a source download alone does not activate a hosted service. Self-hosters create their own bot using the operator guide.
