import hashlib
import hmac
import secrets
import time
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.db import now
from app.models import Agent, PairingCode, RateBucket


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(db, key: str, limit: int, seconds: int):
    # One shared row per principal, locked in PostgreSQL; no process-local bypass.
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    window = int(time.time()) // seconds
    db.execute(
        insert(RateBucket)
        .values(key=key, window=window, count=0)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    bucket = db.scalar(select(RateBucket).where(RateBucket.key == key).with_for_update())
    if bucket.window != window:
        bucket.window, bucket.count = window, 0
    bucket.updated_at = int(time.time())
    bucket.count += 1
    if bucket.count > limit:
        raise HTTPException(429, "RATE_LIMITED")


def pairing_code(db, user):
    rate_limit(db, "link:" + user.id, 5, 600)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    code = "-".join(raw[i : i + 4] for i in range(0, 12, 4))
    db.add(
        PairingCode(
            user_id=user.id, code_hash=digest(code), expires_at=now() + timedelta(minutes=10)
        )
    )
    return code


def authenticate(db, agent_id: str, authorization: str):
    if not authorization.startswith("Bearer ") or len(authorization) > 256:
        raise HTTPException(401, "INVALID_AGENT_TOKEN")
    agent = db.get(Agent, agent_id)
    supplied = digest(authorization[7:])
    expected = agent.secret_hash if agent else "0" * 64
    valid = hmac.compare_digest(supplied, expected)
    if not valid or not agent or agent.revoked_at:
        raise HTTPException(401, "INVALID_AGENT_TOKEN")
    return agent
