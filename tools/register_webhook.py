"""Configure the Telegram service, or inspect it with --check. Never print tokens."""

import argparse
import asyncio
import json
from urllib.parse import urlsplit

from aiogram import Bot
from aiogram.types import BotCommand
from app.config import Settings, settings

COMMANDS = [
    BotCommand(command="link", description="Pair an MT5 agent or select account"),
    BotCommand(command="be", description="Preview breakeven protection by volume"),
    BotCommand(command="close", description="Preview closing worst-cost lots first"),
]


def validate_config(config: Settings) -> str:
    origin = urlsplit(config.public_url)
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or origin.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("PUBLIC_URL must be a public HTTPS origin, without credentials or a path")
    if not config.telegram_bot_token.get_secret_value():
        raise ValueError("Set TELEGRAM_BOT_TOKEN in the protected environment file")
    secret = config.telegram_webhook_secret.get_secret_value()
    if not 32 <= len(secret) <= 256 or any(
        c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in secret
    ):
        raise ValueError(
            "Use 32–256 letters, digits, underscores or hyphens for the webhook secret"
        )
    if not config.telegram_bot_username or config.telegram_bot_username.startswith("@"):
        raise ValueError("Set TELEGRAM_BOT_USERNAME without the @ prefix")
    return config.public_url.rstrip("/") + "/v1/telegram/webhook"


async def configure(bot, config: Settings, *, check=False, drop_pending=False):
    url = validate_config(config)
    identity = await bot.get_me()
    if (identity.username or "").lower() != config.telegram_bot_username.lower():
        raise ValueError("TELEGRAM_BOT_USERNAME does not match this token's bot identity")
    if not check:
        await bot.set_my_commands(COMMANDS)
        await bot.set_my_description(
            "Anchor connects Telegram to your own MT5 risk agent. "
            "Use /link to pair, /be to preview breakeven protection, and /close to preview "
            "reducing existing positions. Both actions require confirmation."
        )
        await bot.set_webhook(
            url,
            secret_token=config.telegram_webhook_secret.get_secret_value(),
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=drop_pending,
        )
    info = await bot.get_webhook_info()
    if info.url != url:
        raise ValueError("Webhook is not registered at PUBLIC_URL; run setup without --check")
    return {
        "bot_url": f"https://t.me/{identity.username}",
        "webhook_url": info.url,
        "pending_updates": info.pending_update_count,
        "telegram_reported_delivery_error": bool(info.last_error_date),
        "mode": "checked" if check else "configured",
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Inspect without modifying Telegram")
    parser.add_argument(
        "--drop-pending-updates",
        action="store_true",
        help="Explicitly discard Telegram's historical pending updates",
    )
    args = parser.parse_args()
    config = settings()
    try:
        validate_config(config)
        async with Bot(config.telegram_bot_token.get_secret_value()) as bot:
            result = await configure(
                bot, config, check=args.check, drop_pending=args.drop_pending_updates
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        # Third-party HTTP errors can include token-bearing Telegram URLs.
        raise SystemExit(
            "Telegram setup failed. Check token, HTTPS connectivity and bot settings."
        ) from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
