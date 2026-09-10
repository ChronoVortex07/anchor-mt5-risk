"""Small in-process sweeper; PostgreSQL locks make multiple API processes safe."""

import asyncio
from datetime import timedelta

import structlog
from sqlalchemy import delete, select

from app import service
from app.db import Session, now
from app.models import Account, Command, PairingCode, RateBucket, Update, WebSession

log = structlog.get_logger()


def sweep_once():
    with Session.begin() as db:
        # Bounded batch; never wait behind an active account transaction.
        ids = select(Command.account_id).where(
            Command.expires_at <= now(),
            Command.status.in_(("PENDING", "LEASED", "AWAITING_CONFIRMATION")),
        )
        accounts = db.scalars(
            select(Account).where(Account.id.in_(ids)).with_for_update(skip_locked=True).limit(100)
        )
        for account in accounts:
            service.expire(db, account)
        db.execute(delete(WebSession).where(WebSession.expires_at < now()))
        db.execute(delete(PairingCode).where(PairingCode.expires_at < now() - timedelta(days=1)))
        db.execute(delete(Update).where(Update.created_at < now() - timedelta(days=7)))
        # Rate rows for unknown IPs are bounded by a 1-day idle window.
        import time

        db.execute(delete(RateBucket).where(RateBucket.updated_at < int(time.time()) - 86400))


async def sweep_loop():
    while True:
        try:
            await asyncio.to_thread(sweep_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.error("MAINTENANCE_FAILED")
        await asyncio.sleep(2)
