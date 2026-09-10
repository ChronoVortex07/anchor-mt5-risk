import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, now

J = JSON().with_variant(JSONB, "postgresql")


def uid():
    return str(uuid.uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class User(Identity, Base):
    __tablename__ = "users"
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    selected_account_id: Mapped[str | None] = mapped_column(String(36))


class Account(Identity, Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (UniqueConstraint("mt5_login", "mt5_server"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    mt5_login: Mapped[int] = mapped_column(BigInteger)
    mt5_server: Mapped[str] = mapped_column(String(120))
    margin_mode: Mapped[str] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="OFFLINE")


class Agent(Identity, Base):
    __tablename__ = "agents"
    account_id: Mapped[str] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(64), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(36))
    secret_hash: Mapped[str] = mapped_column(String(64))
    protocol_version: Mapped[int] = mapped_column(default=1)
    ea_version: Mapped[str] = mapped_column(String(32))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    state: Mapped[dict] = mapped_column(J, default=dict)
    __table_args__ = (
        Index(
            "one_active_agent",
            "account_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )


class PairingCode(Identity, Base):
    __tablename__ = "pairing_codes"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class Mapping(Identity, Base):
    __tablename__ = "symbol_mappings"
    account_id: Mapped[str] = mapped_column(ForeignKey("trading_accounts.id"))
    alias: Mapped[str] = mapped_column(String(64))
    actual_symbol: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("account_id", "alias"),)


ACTIVE = "status IN ('PENDING', 'LEASED', 'AWAITING_CONFIRMATION', 'UNCERTAIN')"


class Command(Identity, Base):
    __tablename__ = "commands"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("trading_accounts.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    delivery_session_id: Mapped[str | None] = mapped_column(String(36))
    leased_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    __table_args__ = (
        Index(
            "one_inflight_per_account",
            "account_id",
            unique=True,
            postgresql_where=text(ACTIVE),
            sqlite_where=text(ACTIVE),
        ),
    )


class Result(Identity, Base):
    __tablename__ = "command_results"
    command_id: Mapped[str] = mapped_column(ForeignKey("commands.id"), unique=True)
    overall_status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict] = mapped_column(J)
    position_results: Mapped[list] = mapped_column(J)


class Audit(Identity, Base):
    __tablename__ = "audit_events"
    user_id: Mapped[str | None] = mapped_column(String(36))
    account_id: Mapped[str | None] = mapped_column(String(36))
    agent_id: Mapped[str | None] = mapped_column(String(36))
    command_id: Mapped[str | None] = mapped_column(String(36))
    event: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(J, default=dict)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger)
    count: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)


class Update(Base):
    __tablename__ = "telegram_updates"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Outbox(Identity, Base):
    __tablename__ = "telegram_outbox"
    chat_id: Mapped[int] = mapped_column(BigInteger)
    body: Mapped[dict] = mapped_column(J)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt: Mapped[datetime] = mapped_column(DateTime, default=now)


class WebSession(Identity, Base):
    __tablename__ = "web_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
