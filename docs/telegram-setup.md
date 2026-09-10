# Host your own Anchor Telegram service

This guide is for the **service operator**. Traders use [the trader quickstart](trader-quickstart.md). The service runs on Linux; each trader runs the EA in their own Windows MT5 terminal. No broker password is sent to the service.

## 1. Create the bot in Telegram

1. Open the verified [@BotFather](https://t.me/BotFather) account in Telegram.
2. Send `/newbot`. Choose a display name, then an available username ending in `bot` (for example, your own `MyAnchorRiskBot`). The example is not a published project bot.
3. BotFather returns an API token. Save it in a password manager and the server's protected `.env` file. **Do not send it to traders, put it in Git, or include it in screenshots.**
4. Record the bot's actual username without `@`. Its access link is `https://t.me/<your_bot_username>`.
5. In BotFather, use `/setjoingroups` to disable adding it to groups. Anchor only accepts private-chat control messages.
6. Once your hostname is chosen, use `/setdomain`, select the bot, and enter that hostname (for example `risk.example.com`) to enable dashboard Telegram sign-in.

Telegram requires this owner interaction; the application cannot create a BotFather identity for you. See [Telegram's official bot tutorial](https://core.telegram.org/bots/tutorial).

## 2. Prepare the Linux host

Use a small VPS with Docker Engine, Docker Compose v2.24.4 or later, a public DNS hostname and TCP ports 80/443 available. PostgreSQL is private. SSH should use keys. If the server already has a reverse proxy, follow the [existing-gateway deployment option](deployment.md) instead of starting another proxy on ports 80/443.

```bash
git clone https://github.com/ChronoVortex07/anchor-mt5-risk.git
cd anchor-mt5-risk
cp .env.example .env
chmod 600 .env
```

Generate two different secrets, once for the database password and once for the webhook secret:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Edit `.env` with a local editor (do not put the bot token into a command line). Set:

```dotenv
POSTGRES_PASSWORD=<first generated hex secret>
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_BOT_USERNAME=<actual bot username without @>
TELEGRAM_WEBHOOK_SECRET=<second generated hex secret>
PUBLIC_URL=https://risk.example.com
PUBLIC_HOST=risk.example.com
ACME_EMAIL=you@example.com
```

Replace the example hostname/email. `PUBLIC_URL` must be the public HTTPS origin, without a path, username/password, query or trailing endpoint. The application and Telegram share the separate webhook secret to authenticate webhook deliveries; traders never need it. Never change an initialized PostgreSQL volume's password merely by editing `.env`; rotate it in PostgreSQL too.

## 3. Start the backend and HTTPS service

Point DNS at your VPS first. On a standalone VPS:

```bash
docker compose --env-file .env -p mt5-risk-prod \
  -f infra/compose.yaml -f infra/compose.production.yaml up -d --build --wait
curl --fail https://risk.example.com/healthz
curl --fail https://risk.example.com/readyz
```

Caddy obtains the TLS certificate. FastAPI hosts the Telegram webhook and the dashboard in the same container; there is no additional Telegram worker or Redis to operate. Its in-process outbox delivers bot messages durably using PostgreSQL. The endpoint must be reachable by Telegram and MT5 without an interactive access/login page. If using a tunnel or existing proxy, preserve the `X-Telegram-Bot-Api-Secret-Token` header and route `/v1/telegram/webhook` and `/v1/agent/*` unchanged.

`docker compose ... --wait` proves local health, not public DNS/TLS. Check both public URLs before proceeding. Local-only development (`infra/compose.yaml` by itself) is useful for tests, but its `127.0.0.1:18089` address cannot receive public Telegram webhooks.

## 4. Register the Telegram webhook and commands

Use the same project name and environment as the running backend:

```bash
docker compose --env-file .env -p mt5-risk-prod -f infra/compose.yaml \
  exec -T backend python -m tools.register_webhook --drop-pending-updates
```

This verifies the token's bot username, sets the description and **three-command menu**, registers `/v1/telegram/webhook` with its secret, and checks the registered URL. The explicit `--drop-pending-updates` flag discards historical messages on first setup. Omit it for ordinary reconfiguration when pending updates should be retained.

Successful output contains your **real Telegram bot link**, webhook URL and pending-update count. It never prints the token. Inspect later without changing Telegram settings:

```bash
docker compose --env-file .env -p mt5-risk-prod -f infra/compose.yaml \
  exec -T backend python -m tools.register_webhook --check
```

The Bot API's [setWebhook and secret-token authentication](https://core.telegram.org/bots/api#setwebhook) document the transport contract. A successful registration alone does not prove delivery: complete the next step.

## 5. Test access and pairing

1. Open the printed `https://t.me/<your_bot_username>` link, press **Start**, then send `/link` in the private chat. Telegram's Start button opens the conversation; `/link` begins pairing.
2. Expect a 10-minute one-use pairing code, the API URL, EA download link and installation guide.
3. Follow [the trader quickstart](trader-quickstart.md) on a **demo hedging account**, initially with `ExecutionEnabled=false`.
4. Confirm the dashboard shows the expected account suffix/server. Map `gold` to its exact broker symbol.
5. Request `/be gold 50` and `/close gold 50`; inspect previews. Execution remains blocked while the EA's local switch is off.
6. Complete the [demo checklist](demo-checklist.md) before enabling trade modifications. MQL5 compilation/broker validation is still a release gate for this source prerelease.

Share **only** these public items with traders: the actual bot link, your HTTPS API/dashboard URL, and the [EA release download](https://github.com/ChronoVortex07/anchor-mt5-risk/releases/tag/v0.1.0-alpha.1). Do not share operator secrets.

## Troubleshooting

| Symptom | Check |
|---|---|
| Bot does not answer `/link` | Confirm private chat, correct bot, successful webhook setup, public HTTPS readiness and backend logs. |
| Setup says username mismatch | `TELEGRAM_BOT_USERNAME` must match the bot that issued the token; omit `@`. |
| Webhook shows delivery errors/pending updates | Check DNS/certificate, proxy forwarding, endpoint access and webhook secret. Recreate backend after changing `.env`, then re-register. |
| Dashboard Login Widget fails | Set BotFather `/setdomain` to the exact dashboard hostname; use HTTPS and the same Telegram account. |
| EA WebRequest fails | Add the exact origin to MT5's allowed WebRequest list; check certificate and network access. |
| `EXECUTION_DISABLED` | Expected until explicitly enabled locally after demo validation. |
| `AGENT_OFFLINE` | MT5 desktop must stay running and connected. Installing the mobile app alone cannot run the EA. |
| `ACCOUNT_MISMATCH` or uncertainty block | Follow the runbook; do not delete journals or blindly repeat a close. |

Safe diagnostics:

```bash
docker compose --env-file .env -p mt5-risk-prod -f infra/compose.yaml ps
docker compose --env-file .env -p mt5-risk-prod -f infra/compose.yaml logs --tail 100 backend
```

Before operating publicly, configure [encrypted offsite backups and restore tests](backup-restore.md). See [remaining risks](remaining-risks.md) and the [operations runbook](operations-runbook.md) for rotation/recovery.
