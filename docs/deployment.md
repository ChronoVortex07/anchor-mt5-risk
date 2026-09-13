# Deployment

## Local development on Linux

Use a dedicated source checkout. If your server already uses Caddy, keep unrelated application and gateway infrastructure intact. Development Compose uses project `mt5-risk-dev`, an isolated PostgreSQL volume, and **127.0.0.1:18089** only. PostgreSQL has no published port. The default backend can start without Telegram credentials for inspection/tests.

```bash
docker compose --env-file .env -f infra/compose.yaml up -d --build --wait
docker compose --env-file .env -f infra/compose.yaml logs --tail 50 backend
docker compose --env-file .env -f infra/compose.yaml stop
```

`.env` must be mode 0600 and excluded from Git. Generate a DB password using `python3 -c 'import secrets; print(secrets.token_hex(24))'`; keep it URL-safe because it enters a PostgreSQL DSN. Fill bot token, bot username (without @), a 32+ random-character webhook secret, and `PUBLIC_URL` before external integration. Do not use example secrets.

## Existing gateway integration

Use `infra/compose.edge.yaml` as an overlay. It removes backend host ports and joins external network `edge` with unique alias `mt5-risk-api`. A reviewable Caddy route is:

```caddyfile
risk.example.com {
    header Strict-Transport-Security "max-age=31536000"
    request_body { max_size 64KB }
    reverse_proxy mt5-risk-api:8080
}
```

Start with `docker compose --env-file .env -p mt5-risk-stage -f infra/compose.yaml -f infra/compose.edge.yaml up -d --build --wait`. Configure the existing hostname/tunnel/gateway separately according to your existing gateway configuration. The repository does **not** change that gateway or expose a public hostname automatically. Telegram webhooks and EA requests must not be intercepted by an interactive Cloudflare Access login page; authenticate these routes with their protocol credentials.

Caddy overwrites untrusted forwarding headers. Uvicorn is configured to trust its forwarding headers because production backend access is restricted to the proxy network. Do not publish backend directly to the Internet. A hostile peer on a shared edge network can forge client IP headers; isolate the network if that assumption is unacceptable.

## Cloudflare Tunnel with the edge overlay

When the existing `cloudflared` connector is attached to the same Docker `edge` network, it can route directly to the backend:

| Cloudflare published application field | Value |
|---|---|
| Public hostname | Your chosen hostname, such as `mt5.chronovortex.dev` |
| Path | Leave blank |
| Service type | **HTTP** |
| Service URL | **`mt5-risk-api:8080`** |

The public URL remains **HTTPS**. HTTP here describes the private Docker connection from the tunnel connector to the backend. No host port is published. Cloudflare documents this [HTTPS-to-HTTP proxy behavior](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/protocols/).

Set `PUBLIC_URL=https://<your-hostname>` in `.env`, then recreate the backend with both Compose files. Keep the same Compose project name when applying the overlay to an existing deployment so its database volume is preserved.

Do not require an interactive Cloudflare Access login for this hostname: Telegram and MT5 cannot complete it. If a wildcard Access application covers the domain, configure an exception scoped to this exact hostname; preserve protections on other hostnames. The app uses its own Telegram login, webhook secret and agent tokens. Avoid browser challenges and cache overrides on API routes. Verify `/healthz` returns JSON over public HTTPS before registering the webhook. For dashboard sign-in, register the exact HTTPS origin in the BotFather mini app → your bot → Login Widget → Allowed URLs.

## Standalone small VPS

1. Install Docker Engine/Compose; configure key-only SSH and disable password/root login after verifying your key works. Configure OS security updates and reliable time synchronization.
2. Copy this repository and a new 0600 `.env`. Set `PUBLIC_HOST`, `PUBLIC_URL=https://<host>`, `ACME_EMAIL`, and all Telegram secrets. Point DNS to the VPS.
3. Restrict inbound traffic to SSH from your administration sources and public TCP 80/443. If using UFW, allow SSH before enabling it. Docker published ports bypass some UFW rules; enforce provider firewall rules too. This stack publishes no PostgreSQL port and removes the development backend port in the production overlay.
4. Start:

```bash
docker compose --env-file .env -p mt5-risk-prod \
  -f infra/compose.yaml -f infra/compose.production.yaml up -d --build --wait
```

Caddy obtains/renews HTTPS certificates; port 80 exists only for redirects/ACME. Backend and database have restart policies, health checks, bounded container logs; backend runs as UID 10001 with read-only filesystem, no capabilities, and temporary `/tmp`. Images are pinned by digest; Python and npm dependencies are locked. Review/update dependency/image pins before production release. Compose image tag defaults to `mt5-risk:0.1.0`; use immutable release tags for subsequent upgrades.

5. Verify `/healthz` and `/readyz` through HTTPS. `/readyz` queries the migration table. Register the bot webhook explicitly:

```bash
docker compose --env-file .env -p mt5-risk-prod -f infra/compose.yaml \
  exec backend python -m tools.register_webhook --drop-pending-updates
```

The explicit `--drop-pending-updates` option discards historical pending Telegram updates; omit it when reconfiguring if pending updates should be retained. Bot command registration advertises exactly `/link`, `/be`, `/close`. Register the dashboard HTTPS origin in BotFather mini app → Login Widget → Allowed URLs. Bot/user interactions must be private chats.

6. Install/test the EA on a demo account. Configure and test offsite backups before enabling live operations.

## Upgrades

Back up and perform a restore test first. Stop new commands, wait for active operations to finish or reconcile them, build the new image, then restart backend. The backend applies Alembic migrations at startup. Do not run simultaneous migration processes; this deployment uses one backend instance. For rollback, prefer a forward fix; database downgrade/restore may erase audit evidence and must be planned separately. Restoring a DB can resurrect old LEASED commands; deadlines and uncertainty blocking must remain enforced and all previously active executions reconciled.

Web dashboard sessions are Secure/HttpOnly/SameSite=Strict; direct HTTP preview is for local inspection only. CORS is not opened. Avoid access logs containing Telegram signed-login query strings. Application logs intentionally omit access URLs/auth headers and redact Telegram exceptions. Database backups and full login numbers are sensitive; use encrypted offsite storage.
