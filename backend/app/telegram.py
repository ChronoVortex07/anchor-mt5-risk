import asyncio
import base64
import hashlib
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import structlog
from aiogram import Bot
from aiogram.types import BotCommand, Update
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from app import service
from app.config import settings
from app.db import Session, now
from app.links import EA_DOWNLOAD_URL, SETUP_URL
from app.models import Outbox
from app.models import Update as StoredUpdate
from app.schemas import Intent
from app.security import pairing_code

log = structlog.get_logger()


def cipher():
    key = hashlib.sha256(settings().telegram_bot_token.get_secret_value().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def parse_command(text):
    parts = text.split()
    if not parts:
        service.fail("EMPTY_COMMAND", 422)
    action = parts.pop(0).split("@")[0].removeprefix("/").lower()
    if action == "link" and not parts:
        return action, None
    if action not in ("be", "close") or not 1 <= len(parts) <= 3:
        service.fail("Use /link, /be <symbol> [buy|sell] [pct], /close <symbol> [pct].", 422)
    symbol = parts.pop(0)
    side = "AUTO" if action == "be" else "BOTH"
    if parts and parts[0].lower() in ("buy", "sell"):
        side = parts.pop(0).upper()
    if len(parts) > 1:
        service.fail("INVALID_ARGUMENTS", 422)
    try:
        pct = Decimal(parts[0]) if parts and parts[0].lower() != "all" else Decimal(100)
        if not pct.is_finite() or not 0 < pct <= 100:
            raise ValueError
        intent = Intent(symbol=symbol, side=side, target_fraction=float(pct / 100))
    except (InvalidOperation, ValueError):
        service.fail("Percentage must be greater than 0 and at most 100.", 422)
    return action, intent


def handle_update(db, raw):
    update = Update.model_validate(raw)
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    inserted = db.execute(
        insert(StoredUpdate)
        .values(id=update.update_id)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(StoredUpdate.id)
    ).scalar()
    if inserted is None:
        return
    msg = update.message
    cb = update.callback_query
    human = msg.from_user if msg else cb.from_user if cb else None
    chat = msg.chat if msg else cb.message.chat if cb and cb.message else None
    # Private chats only; forwarded identities and channel authors never authenticate.
    if not human or human.is_bot or not chat or chat.type != "private" or chat.id != human.id:
        return
    user = service.get_user(db, human.id, human.username)
    try:
        with db.begin_nested():
            if cb:
                data = (cb.data or "").split(":", 1)
                if len(data) != 2:
                    service.fail("INVALID_CALLBACK", 422)
                verb, item = data
                if verb in ("confirm", "cancel"):
                    command = service.confirm(db, user, item, cancel=verb == "cancel")
                    service.notify(db, user.id, f"Operation {command.status.lower()}.")
                elif verb == "use":
                    account = service.owned_account(db, user, item)
                    user.selected_account_id = account.id
                    service.notify(db, user.id, f"Selected {account.label}.")
                else:
                    service.fail("INVALID_CALLBACK", 422)
            elif msg and msg.text:
                action, intent = parse_command(msg.text)
                if action == "link":
                    code = pairing_code(db, user)
                    service.audit(db, "USER_LINK_REQUESTED", user_id=user.id)
                    body = {
                        "text": f"Pairing code: {code}\nExpires in 10 minutes; one use.\n"
                        f"EA ApiUrl: {settings().public_url}\n"
                        "Keep ExecutionEnabled=false while testing.\n"
                        f"Account settings: {settings().public_url}\n"
                        f"Download EA source: {EA_DOWNLOAD_URL}\n"
                        f"Installation guide: {SETUP_URL}"
                    }
                    accounts = service.accounts_view(db, user)
                    if accounts:
                        body["reply_markup"] = {
                            "inline_keyboard": [
                                [service.button("Use " + a["label"], "use:" + a["id"])]
                                for a in accounts
                            ]
                        }
                    # Pairing codes must not be plaintext at rest, including delivery queue.
                    sealed = cipher().encrypt(json.dumps(body).encode()).decode()
                    db.add(Outbox(chat_id=human.id, body={"sealed": sealed}))
                else:
                    command = service.request_preview(
                        db,
                        user,
                        action,
                        intent.symbol,
                        intent.target_fraction,
                        intent.side,
                        f"telegram:{update.update_id}",
                    )
                    service.notify(
                        db,
                        user.id,
                        f"Requesting live preview. Operation {command.id[:8]} expires shortly.",
                    )
    except HTTPException as exc:
        service.notify(db, user.id, str(exc.detail))


async def deliver_once(bot):
    # Multiple API workers are safe: row lock is held through send. Telegram has no
    # sendMessage idempotency key, so a crash after send can duplicate a notification.
    with Session.begin() as db:
        item = db.scalar(
            select(Outbox)
            .where(Outbox.sent_at.is_(None), Outbox.next_attempt <= now())
            .order_by(Outbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not item:
            return False
        if (now() - item.created_at).total_seconds() > 600:
            item.body, item.sent_at = {"expired": True}, now()
            return True
        body = item.body
        if "sealed" in body:
            body = json.loads(cipher().decrypt(body["sealed"].encode()))
        try:
            await bot.send_message(chat_id=item.chat_id, **body, request_timeout=5)
            item.sent_at, item.body = now(), {"delivered": True}
        except Exception:
            # Do not log exception text: Telegram library errors may contain token URLs.
            item.attempts += 1
            item.next_attempt = now() + timedelta(seconds=min(60, 2 ** min(item.attempts, 6)))
            log.warning("TELEGRAM_DELIVERY_FAILED", outbox_id=item.id, attempts=item.attempts)
        return True


async def outbox_loop():
    token = settings().telegram_bot_token.get_secret_value()
    if not token:
        return
    async with Bot(token) as bot:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="link", description="Pair an MT5 agent or select account"),
                    BotCommand(command="be", description="Preview breakeven protection by volume"),
                    BotCommand(
                        command="close", description="Preview closing worst-cost lots first"
                    ),
                ]
            )
        except Exception:
            log.warning("TELEGRAM_COMMAND_REGISTRATION_FAILED")
        while True:
            try:
                pending = await deliver_once(bot)
                await asyncio.sleep(0.1 if pending else 0.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("OUTBOX_WORKER_FAILED")
                await asyncio.sleep(2)
