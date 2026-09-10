import secrets
from datetime import timedelta

import structlog
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.db import now
from app.models import Account, Agent, Audit, Command, Mapping, Outbox, PairingCode, Result, User
from app.schemas import Intent
from app.security import digest

log = structlog.get_logger()
ACTIVE = ("PENDING", "LEASED", "AWAITING_CONFIRMATION", "UNCERTAIN")
EXECUTIONS = ("PROTECT_BREAKEVEN", "REDUCE_EXPOSURE")


def fail(code, status=409):
    raise HTTPException(status, code)


def audit(db, event, **ids):
    db.add(Audit(event=event, **ids))
    log.info(event, **{k: v for k, v in ids.items() if k != "details"})


def notify(db, user_id, text, buttons=None):
    user = db.get(User, user_id)
    body = {"text": text}
    if buttons:
        body["reply_markup"] = {"inline_keyboard": buttons}
    db.add(Outbox(chat_id=user.telegram_user_id, body=body))


def button(text, data):
    return {"text": text, "callback_data": data}


def get_user(db, telegram_id, username=None):
    # Serializes concurrent first updates for the same human, including web login.
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(
        insert(User)
        .values(telegram_user_id=telegram_id, telegram_username=username)
        .on_conflict_do_nothing(index_elements=["telegram_user_id"])
    )
    return db.scalar(select(User).where(User.telegram_user_id == telegram_id).with_for_update())


def owned_account(db, user, account_id, lock=False):
    query = select(Account).where(Account.id == account_id, Account.user_id == user.id)
    account = db.scalar(query.with_for_update() if lock else query)
    if not account:
        fail("ACCOUNT_NOT_FOUND", 404)
    return account


def active_agent(db, account_id):
    agent = db.scalar(
        select(Agent).where(Agent.account_id == account_id, Agent.revoked_at.is_(None))
    )
    if not agent:
        fail("NO_AGENT")
    return agent


def pair(db, body):
    code = db.scalar(
        select(PairingCode)
        .where(PairingCode.code_hash == digest(body.pairing_code))
        .with_for_update()
    )
    if not code or code.used_at or code.expires_at <= now():
        fail("INVALID_PAIRING_CODE", 401)
    user = db.scalar(select(User).where(User.id == code.user_id).with_for_update())
    # Lock order is human then account, consistent with Telegram updates.
    account = db.scalar(
        select(Account)
        .where(Account.mt5_login == body.account.login, Account.mt5_server == body.account.server)
        .with_for_update()
    )
    if account:
        if account.user_id != code.user_id:
            fail("ACCOUNT_ALREADY_BOUND")
        if db.scalar(
            select(Agent.id).where(Agent.account_id == account.id, Agent.revoked_at.is_(None))
        ):
            fail("REVOKE_EXISTING_AGENT_FIRST")
        if account.status == "BLOCKED_UNCERTAIN":
            fail("RECONCILIATION_REQUIRED")
    else:
        account = Account(
            user_id=code.user_id,
            label=f"MT5 •{str(body.account.login)[-4:]}",
            mt5_login=body.account.login,
            mt5_server=body.account.server,
            margin_mode=body.account.margin_mode,
        )
        db.add(account)
        db.flush()
    if db.scalar(select(Agent.id).where(Agent.installation_id == str(body.installation_id))):
        fail("INSTALLATION_ALREADY_PAIRED")
    secret = secrets.token_urlsafe(32)
    agent = Agent(
        account_id=account.id,
        installation_id=str(body.installation_id),
        secret_hash=digest(secret),
        session_id=str(body.session_id),
        ea_version=body.ea_version,
    )
    db.add(agent)
    code.used_at = now()
    user = db.get(User, code.user_id)
    if not user.selected_account_id:
        user.selected_account_id = account.id
    db.flush()
    audit(db, "AGENT_PAIRED", user_id=user.id, account_id=account.id, agent_id=agent.id)
    notify(
        db,
        user.id,
        f"Paired {account.label} on {account.mt5_server}. "
        "Set an exact symbol mapping in the dashboard, or use the broker's exact symbol.",
    )
    return {"agent_id": agent.id, "agent_secret": secret, "protocol_version": 1}


def expire(db, account):
    for command in db.scalars(
        select(Command).where(Command.account_id == account.id, Command.status.in_(ACTIVE))
    ):
        if command.expires_at > now() or command.status == "UNCERTAIN":
            continue
        if command.status == "LEASED" and command.type in EXECUTIONS:
            command.status = "UNCERTAIN"
            account.status = "BLOCKED_UNCERTAIN"
            notify(
                db,
                command.user_id,
                "Execution outcome is uncertain. Account blocked pending "
                "a result or operator reconciliation. Do not repeat the close manually blindly.",
            )
        else:
            command.status = "EXPIRED"
            command.completed_at = now()
        audit(db, "COMMAND_" + command.status, command_id=command.id, account_id=account.id)
    db.flush()


def available(db, account, execution=False):
    expire(db, account)
    if account.status in ("BLOCKED_UNCERTAIN", "ACCOUNT_MISMATCH"):
        fail(account.status)
    agent = active_agent(db, account.id)
    if (
        not agent.last_seen_at
        or (now() - agent.last_seen_at).total_seconds() > settings().online_seconds
    ):
        fail("AGENT_OFFLINE")
    if account.margin_mode != "RETAIL_HEDGING":
        fail("NOT_HEDGING")
    if not agent.state.get("terminal", {}).get("connected"):
        fail("TERMINAL_OFFLINE")
    if execution and not agent.state.get("execution_enabled"):
        fail("EXECUTION_DISABLED")
    return agent


def resolve(db, account_id, identifier):
    mapping = db.scalar(
        select(Mapping).where(Mapping.account_id == account_id, Mapping.alias == identifier.lower())
    )
    return mapping.actual_symbol if mapping else identifier


def request_preview(db, user, action, identifier, fraction, side, key):
    if action not in ("be", "close"):
        fail("UNSUPPORTED_COMMAND", 422)
    account = owned_account(db, user, user.selected_account_id, lock=True)
    existing = db.scalar(
        select(Command).where(Command.idempotency_key == key, Command.user_id == user.id)
    )
    if existing:
        return existing
    agent = available(db, account)
    if db.scalar(
        select(Command.id).where(Command.account_id == account.id, Command.status.in_(ACTIVE))
    ):
        fail("OPERATION_IN_PROGRESS")
    payload = Intent(
        symbol=resolve(db, account.id, identifier), target_fraction=fraction, side=side
    ).model_dump()
    kind = "PREVIEW_PROTECT_BREAKEVEN" if action == "be" else "PREVIEW_REDUCE_EXPOSURE"
    command = Command(
        user_id=user.id,
        account_id=account.id,
        agent_id=agent.id,
        type=kind,
        payload=payload,
        idempotency_key=key,
        expires_at=now() + timedelta(seconds=settings().command_ttl_seconds),
    )
    db.add(command)
    db.flush()
    audit(db, "COMMAND_CREATED", user_id=user.id, account_id=account.id, command_id=command.id)
    return command


def confirm(db, user, command_id, cancel=False):
    preview = db.scalar(select(Command).where(Command.id == command_id, Command.user_id == user.id))
    if not preview:
        fail("COMMAND_NOT_FOUND", 404)
    account = owned_account(db, user, preview.account_id, lock=True)
    db.refresh(preview)
    existing = db.scalar(select(Command).where(Command.idempotency_key == "confirm:" + preview.id))
    if existing and not cancel:
        return existing
    expire(db, account)
    if preview.status != "AWAITING_CONFIRMATION" or preview.expires_at <= now():
        fail("PREVIEW_EXPIRED_OR_CONSUMED")
    if cancel:
        preview.status, preview.completed_at = "CANCELLED", now()
        audit(db, "COMMAND_CANCELLED", command_id=preview.id, user_id=user.id)
        return preview
    agent = available(db, account, execution=True)
    if agent.id != preview.agent_id:
        fail("AGENT_CHANGED")
    preview.status, preview.completed_at = "SUCCEEDED", now()
    db.flush()  # releases partial unique index before creating execution
    command = Command(
        user_id=user.id,
        account_id=account.id,
        agent_id=agent.id,
        type=preview.type.removeprefix("PREVIEW_"),
        payload=preview.payload,
        idempotency_key="confirm:" + preview.id,
        confirmed_at=now(),
        expires_at=now() + timedelta(seconds=settings().command_ttl_seconds),
    )
    db.add(command)
    db.flush()
    audit(db, "COMMAND_CONFIRMED", user_id=user.id, command_id=command.id, account_id=account.id)
    return command


def describe_result(command, submission, preview):
    s = submission.summary
    operation = "Close" if "REDUCE" in command.type else "BE+ buffer estimate"
    text = (
        f"{operation} {'preview' if preview else 'result'} — {s.code}\n"
        f"{s.symbol} {s.side}\nGross: {s.total_volume:g} lots "
        f"(BUY {s.buy_volume:g} / SELL {s.sell_volume:g})\n"
        f"Requested: {command.payload['target_fraction'] * 100:g}% "
        f"= {s.requested_volume:g} lots\n"
        f"Already protected: {s.already_protected_volume:g} lots\n"
        f"Planned additional: {s.planned_volume:g} lots\n"
    )
    if not preview:
        text += (
            f"Agent reports broker-confirmed: {s.confirmed_volume:g} lots\n"
            f"Current protected: {s.protected_volume:g} lots\n"
            f"Status: {submission.status}\n"
        )
    text += f"Ineligible: {s.ineligible_positions}\n"
    if s.code == "AMBIGUOUS_SIDE":
        pct = command.payload["target_fraction"] * 100
        text += f"Choose /be {s.symbol} buy {pct:g} or /be {s.symbol} sell {pct:g}.\n"
    if "REDUCE" in command.type:
        text += "Worst-cost lots first. Closing a hedge leg can increase net directional exposure."
    else:
        text += "BE+ is a stop-price buffer, not a guaranteed non-negative fill."
    return text


def accept_result(db, agent, account, submission):
    command = db.scalar(
        select(Command).where(
            Command.id == str(submission.command_id), Command.agent_id == agent.id
        )
    )
    if not command:
        fail("COMMAND_NOT_FOUND", 404)
    old = db.scalar(select(Result).where(Result.command_id == command.id))
    if old:
        if (
            old.overall_status != submission.status
            or old.summary != submission.summary.model_dump()
            or old.position_results != [r.model_dump() for r in submission.position_results]
        ):
            fail("RESULT_CONFLICT")
        return
    if command.status not in ("LEASED", "UNCERTAIN", "EXPIRED") or not command.leased_at:
        fail("COMMAND_NOT_LEASED")
    preview = command.type.startswith("PREVIEW_")
    db.add(
        Result(
            command_id=command.id,
            overall_status=submission.status,
            summary=submission.summary.model_dump(),
            position_results=[r.model_dump() for r in submission.position_results],
        )
    )
    if submission.status == "UNCERTAIN" and not preview:
        command.status = "UNCERTAIN"
        account.status = "BLOCKED_UNCERTAIN"
    elif preview and command.expires_at > now() and submission.status == "SUCCEEDED":
        command.status = "AWAITING_CONFIRMATION"
    elif preview and command.expires_at <= now():
        command.status = "EXPIRED"
    else:
        command.status = submission.status
        command.completed_at = now()
        if account.status == "BLOCKED_UNCERTAIN":
            account.status = "ONLINE"
    audit(
        db,
        "COMMAND_COMPLETED",
        account_id=account.id,
        agent_id=agent.id,
        command_id=command.id,
        details={
            "status": command.status,
            "summary": command.payload,
            "result": submission.model_dump(mode="json"),
        },
    )
    buttons = None
    if command.status == "AWAITING_CONFIRMATION":
        buttons = [
            [button("Confirm", "confirm:" + command.id), button("Cancel", "cancel:" + command.id)]
        ]
    notify(db, command.user_id, describe_result(command, submission, preview), buttons)
    db.flush()


def poll(db, agent, body):
    # Account row serializes pairing, revoke, leasing, results, and command creation.
    account = db.scalar(select(Account).where(Account.id == agent.account_id).with_for_update())
    db.refresh(agent)
    if agent.revoked_at:
        fail("AGENT_REVOKED", 401)
    response = {
        "protocol_version": 1,
        "server_time": now().isoformat() + "Z",
        "poll_after_ms": 1000 + secrets.randbelow(400),
        "command": None,
        "ack_result_id": None,
        "code": "OK",
    }
    if (
        body.account.login != account.mt5_login
        or body.account.server != account.mt5_server
        or str(body.installation_id) != agent.installation_id
    ):
        if account.status != "BLOCKED_UNCERTAIN":
            account.status = "ACCOUNT_MISMATCH"
        audit(db, "ACCOUNT_MISMATCH", agent_id=agent.id, account_id=account.id)
        response["code"] = "ACCOUNT_MISMATCH"
        return response
    if account.status == "ACCOUNT_MISMATCH":
        response["code"] = "REPAIR_REQUIRED"
        return response
    incoming_session = str(body.session_id)
    if (
        agent.session_id
        and agent.session_id != incoming_session
        and agent.last_seen_at
        and (now() - agent.last_seen_at).total_seconds() < 10
    ):
        response["code"] = "AGENT_SESSION_BUSY"
        return response
    agent.session_id = incoming_session
    previous_seen = agent.last_seen_at
    agent.last_seen_at = account.last_seen_at = now()
    agent.state = body.model_dump(mode="json", exclude={"result"})
    agent.ea_version = body.ea_version
    account.margin_mode = body.account.margin_mode
    if account.status != "BLOCKED_UNCERTAIN":
        account.status = "ONLINE"
    if not previous_seen or (now() - previous_seen).total_seconds() > settings().online_seconds:
        audit(db, "AGENT_ONLINE", account_id=account.id, agent_id=agent.id)
    if body.result:
        accept_result(db, agent, account, body.result)
        response["ack_result_id"] = str(body.result.command_id)
    expire(db, account)
    if account.status == "BLOCKED_UNCERTAIN":
        response["code"] = "BLOCKED_UNCERTAIN"
        return response
    command = db.scalar(
        select(Command)
        .where(Command.agent_id == agent.id, Command.status.in_(("PENDING", "LEASED")))
        .order_by(Command.created_at)
        .limit(1)
    )
    if not command:
        return response
    if not body.terminal.connected or body.account.margin_mode != "RETAIL_HEDGING":
        response["code"] = "TERMINAL_UNAVAILABLE"
        return response
    if command.type in EXECUTIONS and not body.execution_enabled:
        response["code"] = "EXECUTION_DISABLED"
        return response
    if (
        command.status == "LEASED"
        and command.type in EXECUTIONS
        and command.delivery_session_id != incoming_session
    ):
        command.status, account.status = "UNCERTAIN", "BLOCKED_UNCERTAIN"
        audit(db, "EXECUTION_SESSION_CHANGED", account_id=account.id, command_id=command.id)
        response["code"] = "BLOCKED_UNCERTAIN"
        return response
    if command.status == "PENDING":
        command.delivery_session_id = incoming_session
        command.status = "LEASED"
        command.leased_at = now()
        command.lease_until = command.expires_at  # never extend on retry
        audit(db, "COMMAND_LEASED", command_id=command.id, agent_id=agent.id)
    remaining = max(0, int((command.expires_at - now()).total_seconds() * 1000))
    response["command"] = {
        "id": command.id,
        "type": command.type,
        "expires_in_ms": remaining,
        **command.payload,
    }
    return response


def revoke(db, user, account_id):
    account = owned_account(db, user, account_id, lock=True)
    expire(db, account)
    active = db.scalar(
        select(Command).where(Command.account_id == account.id, Command.status.in_(ACTIVE))
    )
    agent = active_agent(db, account.id)
    agent.revoked_at = now()
    if active:
        if active.status in ("LEASED", "UNCERTAIN") and active.type in EXECUTIONS:
            active.status, account.status = "UNCERTAIN", "BLOCKED_UNCERTAIN"
        else:
            active.status = "CANCELLED"
    audit(db, "AGENT_REVOKED", user_id=user.id, account_id=account.id, agent_id=agent.id)


def accounts_view(db, user):
    result = []
    for account in db.scalars(select(Account).where(Account.user_id == user.id)):
        agent = db.scalar(
            select(Agent).where(Agent.account_id == account.id, Agent.revoked_at.is_(None))
        )
        age = (now() - agent.last_seen_at).total_seconds() if agent and agent.last_seen_at else 1e9
        status = "ONLINE" if age < 5 else "STALE" if age <= 10 else "OFFLINE"
        if account.status in ("ACCOUNT_MISMATCH", "BLOCKED_UNCERTAIN"):
            status = account.status
        mappings = db.scalars(select(Mapping).where(Mapping.account_id == account.id))
        result.append(
            {
                "id": account.id,
                "label": account.label,
                "server": account.mt5_server,
                "login_suffix": str(account.mt5_login)[-4:],
                "status": status,
                "margin_mode": account.margin_mode,
                "selected": user.selected_account_id == account.id,
                "last_seen_at": agent.last_seen_at.isoformat() + "Z"
                if agent and agent.last_seen_at
                else None,
                "ea_version": agent.ea_version if agent else None,
                "execution_enabled": agent.state.get("execution_enabled", False)
                if agent
                else False,
                "mappings": [
                    {"alias": m.alias, "actual_symbol": m.actual_symbol} for m in mappings
                ],
            }
        )
    return result
