# Contributing

Anchor is MIT-licensed. Open an issue describing the behavior you want to change, or send a pull request with a small reproducible example and relevant tests. Never include broker/Telegram credentials, pairing codes, local agent files or real account screenshots in public issues.

Read [architecture](docs/architecture.md), [protocol](docs/agent-protocol.md), [threat model](docs/threat-model.md) and [testing](docs/testing.md) before changing trading behavior. Keep broker execution inside MQL5. No generic order-entry API, remote TP/SL removal or confirmation bypass should be added to this risk-reduction protocol.

Run Ruff, pytest with disposable PostgreSQL, the frontend build/format/browser checks and the EA packaging tests. MQL5 changes also require compiler logs and demo evidence; identify unrun checks clearly. Network-free pure MQL5 tests are under `mt5/tests`. Do not claim broker correctness from Python simulation alone.

Build the source-only EA archive with `python tools/package_ea.py --output build`. Only `.mq5`/`.mqh` files, installation documents and LICENSE are included. Never attach local credentials, journals or unverified `.ex5` binaries to a release.
