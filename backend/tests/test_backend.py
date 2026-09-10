import copy
import hashlib
import hmac
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from app import service
from app.config import settings
from app.db import now
from app.models import Account, Agent, Command, Mapping, PairingCode, Result, User
from app.schemas import Pair, Poll
from app.security import authenticate, digest, pairing_code
from fake_agent import FakeAgent
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select


def preview(database, user_id, action="be", key="test-1"):
    with database.begin() as db:
        user = db.get(User, user_id)
        return service.request_preview(
            db, user, action, "XAUUSD", 0.5, "AUTO" if action == "be" else "BOTH", key
        ).id


def execute(database, paired, action="be"):
    user_id, agent = paired
    cid = preview(database, user_id, action)
    agent.tick()
    agent.tick()
    with database.begin() as db:
        command = service.confirm(db, db.get(User, user_id), cid)
        execution_id = command.id
    return execution_id


def test_pair_single_use_hash_auth(database, paired):
    user_id, fake = paired
    with database.begin() as db:
        agent = db.get(Agent, fake.credentials["agent_id"])
        assert agent.secret_hash == digest(fake.credentials["agent_secret"])
        assert len(fake.credentials["agent_secret"]) >= 43
        assert (
            authenticate(db, agent.id, "Bearer " + fake.credentials["agent_secret"]).id == agent.id
        )
        with pytest.raises(HTTPException):
            authenticate(db, agent.id, "Bearer wrong")
        code = pairing_code(db, db.get(User, user_id))
        row = db.scalar(select(PairingCode).where(PairingCode.code_hash == digest(code)))
        row.expires_at = now() - timedelta(seconds=1)
        with pytest.raises(HTTPException):
            service.pair(db, Pair.model_validate({**fake.state(), "pairing_code": code}))


def test_pair_code_consumed(database, client):
    with database.begin() as db:
        code = pairing_code(db, service.get_user(db, 999))
    first, second = FakeAgent(client), FakeAgent(client)
    first.pair(code)
    with pytest.raises(httpx.HTTPStatusError):
        second.pair(code)


@pytest.mark.parametrize("action", ["be", "close"])
def test_end_to_end_fake_agent(database, paired, action):
    cid = execute(database, paired, action)
    _, agent = paired
    agent.tick()
    agent.tick()
    with database.begin() as db:
        c = db.get(Command, cid)
        assert c.status == "SUCCEEDED"
        result = db.scalar(select(Result).where(Result.command_id == cid))
        assert result.summary["confirmed_volume"] == 0.3
    # Duplicate delivery returns cached result and cannot apply a second fraction.
    original = copy.deepcopy(agent.positions)
    assert agent.history[cid]["status"] == "SUCCEEDED"
    agent.pending = agent.history[cid]
    agent.tick()
    assert agent.positions == original


def test_cross_user_isolation(database, paired):
    cid = execute(database, paired)
    user_id, fake = paired
    with database.begin() as db:
        user = service.get_user(db, 2002)
        owner = db.get(User, user_id)
        for call in [
            lambda: service.owned_account(db, user, owner.selected_account_id),
            lambda: service.confirm(db, user, cid),
            lambda: service.revoke(db, user, owner.selected_account_id),
        ]:
            with pytest.raises(HTTPException) as exc:
                call()
            assert exc.value.status_code == 404
        user.selected_account_id = owner.selected_account_id
        with pytest.raises(HTTPException):
            service.request_preview(db, user, "be", "XAUUSD", 1, "AUTO", "cross")
        assert service.accounts_view(db, user) == []


def test_account_mismatch_latches(database, paired):
    _, fake = paired
    with database.begin() as db:
        agent = db.get(Agent, fake.credentials["agent_id"])
        state = {**fake.state(), "terminal": {"connected": True}, "execution_enabled": True}
        state["account"]["login"] += 1
        assert service.poll(db, agent, Poll.model_validate(state))["code"] == "ACCOUNT_MISMATCH"
    with database.begin() as db:
        agent = db.get(Agent, fake.credentials["agent_id"])
        state["account"]["login"] -= 1
        assert service.poll(db, agent, Poll.model_validate(state))["code"] == "REPAIR_REQUIRED"


def test_revoke_tokens(database, paired):
    user_id, fake = paired
    with database.begin() as db:
        user = db.get(User, user_id)
        service.revoke(db, user, user.selected_account_id)
    with database.begin() as db, pytest.raises(HTTPException):
        authenticate(db, fake.credentials["agent_id"], "Bearer " + fake.credentials["agent_secret"])


def test_expiry_pending_and_offline(database, paired):
    user_id, fake = paired
    cid = preview(database, user_id)
    with database.begin() as db:
        db.get(Command, cid).expires_at = now() - timedelta(seconds=1)
    assert fake.tick()["command"] is None
    with database.begin() as db:
        assert db.get(Command, cid).status == "EXPIRED"
        db.get(Agent, fake.credentials["agent_id"]).last_seen_at = now() - timedelta(minutes=1)
    with pytest.raises(HTTPException, match="AGENT_OFFLINE"):
        preview(database, user_id, key="offline")


def test_expired_execution_blocks_until_late_result(database, paired):
    cid = execute(database, paired, "close")
    user_id, fake = paired
    fake.tick()  # executes, do not submit yet
    with database.begin() as db:
        c = db.get(Command, cid)
        c.expires_at = now() - timedelta(seconds=1)
        service.expire(db, db.get(Account, c.account_id))
        assert c.status == "UNCERTAIN"
    with pytest.raises(HTTPException):
        preview(database, user_id, key="blocked")
    fake.tick()  # late durable confirmed result reconciles outcome
    with database.begin() as db:
        assert db.get(Command, cid).status == "SUCCEEDED"


def test_result_conflict_and_pre_delivery_rejection(database, paired):
    cid = execute(database, paired)
    _, fake = paired
    fake.tick()
    fake.tick()
    fake.pending = copy.deepcopy(fake.history[cid])
    fake.pending["summary"]["confirmed_volume"] = 100
    with pytest.raises(httpx.HTTPStatusError):
        fake.tick()


def test_uncertain_result_never_unblocks_by_pairing(database, paired):
    cid = execute(database, paired, "close")
    user_id, fake = paired
    fake.failure = "uncertain"
    fake.tick()
    fake.tick()
    with database.begin() as db:
        c = db.get(Command, cid)
        assert c.status == "UNCERTAIN"
        assert db.get(Account, c.account_id).status == "BLOCKED_UNCERTAIN"
        user = db.get(User, user_id)
        service.revoke(db, user, c.account_id)
        code = pairing_code(db, user)
        other = FakeAgent(fake.client)
        with pytest.raises(HTTPException, match="RECONCILIATION_REQUIRED"):
            service.pair(db, Pair.model_validate({**other.state(), "pairing_code": code}))


def test_alias_selection_and_netting(database, paired):
    user_id, fake = paired
    with database.begin() as db:
        user = db.get(User, user_id)
        db.add(Mapping(account_id=user.selected_account_id, alias="gold", actual_symbol="XAUUSD.a"))
        db.flush()
        assert service.resolve(db, user.selected_account_id, "GOLD") == "XAUUSD.a"
        assert service.resolve(db, user.selected_account_id, "XAUUSDm") == "XAUUSDm"
        db.get(Account, user.selected_account_id).margin_mode = "RETAIL_NETTING"
    with pytest.raises(HTTPException, match="NOT_HEDGING"):
        preview(database, user_id)


def test_confirmation_expiry_and_dry_run(database, paired):
    user_id, fake = paired
    cid = preview(database, user_id)
    fake.tick()
    fake.tick()
    fake.execution_enabled = False
    fake.tick()
    with database.begin() as db, pytest.raises(HTTPException, match="EXECUTION_DISABLED"):
        service.confirm(db, db.get(User, user_id), cid)
    with database.begin() as db:
        db.get(Command, cid).expires_at = now() - timedelta(seconds=1)
    with database.begin() as db, pytest.raises(HTTPException, match="PREVIEW_EXPIRED"):
        service.confirm(db, db.get(User, user_id), cid)


def test_webhook_secret_dedup_and_pairing_redaction(database, client, monkeypatch):
    monkeypatch.setattr(settings(), "telegram_webhook_secret", SecretStr("test-hook"))
    body = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": int(time.time()),
            "chat": {"id": 88, "type": "private"},
            "from": {"id": 88, "is_bot": False, "first_name": "Test"},
            "text": "/link",
        },
    }
    assert client.post("/v1/telegram/webhook", json=body).status_code == 401
    for _ in range(2):
        assert (
            client.post(
                "/v1/telegram/webhook",
                json=body,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-hook"},
            ).status_code
            == 200
        )
    with database.begin() as db:
        assert len(list(db.scalars(select(PairingCode)))) == 1


def test_body_limit_and_strict_protocol(client):
    assert client.post("/v1/agent/pair", content="x" * 65537).status_code == 413
    assert client.post("/v1/agent/pair", json={"protocol_version": 2}).status_code == 422


def test_web_login_and_csrf(database, client, paired, monkeypatch):
    token = "123456:test-fake-token"
    monkeypatch.setattr(settings(), "telegram_bot_token", SecretStr(token))
    fields = {"id": 1001, "first_name": "Test", "auth_date": int(time.time())}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    signature = hmac.new(
        hashlib.sha256(token.encode()).digest(), check.encode(), hashlib.sha256
    ).hexdigest()
    assert client.post("/v1/web/login", json={**fields, "hash": signature}).status_code == 200
    accounts = client.get("/v1/web/accounts").json()
    assert len(accounts) == 1 and "mt5_login" not in accounts[0]
    assert client.post(f"/v1/web/accounts/{accounts[0]['id']}/revoke").status_code == 403


def test_parallel_creation_poll_and_result(database, paired):
    if database.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    user_id, fake = paired

    def create(i):
        try:
            return preview(database, user_id, key=f"race-{i}")
        except HTTPException:
            return None

    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(create, range(2)))
    assert len([x for x in ids if x]) == 1
    cid = next(x for x in ids if x)

    def poll_one(_):
        with database.begin() as db:
            agent = db.get(Agent, fake.credentials["agent_id"])
            return service.poll(
                db,
                agent,
                Poll.model_validate(
                    {**fake.state(), "terminal": {"connected": True}, "execution_enabled": True}
                ),
            )

    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(poll_one, range(2)))
    assert all(r["command"]["id"] == cid for r in replies)
    fake.tick()
    submission = copy.deepcopy(fake.pending)

    def submit(_):
        with database.begin() as db:
            agent = db.get(Agent, fake.credentials["agent_id"])
            return service.poll(
                db,
                agent,
                Poll.model_validate(
                    {
                        **fake.state(),
                        "terminal": {"connected": True},
                        "execution_enabled": True,
                        "result": submission,
                    }
                ),
            )

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(submit, range(2)))
    with database.begin() as db:
        assert len(list(db.scalars(select(Result).where(Result.command_id == cid)))) == 1
    # Retry delivery retains original deadline; stale leases are never reassigned.
    with database.begin() as db:
        assert db.get(Command, cid).lease_until == db.get(Command, cid).expires_at


def test_full_telegram_pair_preview_confirmation(database, client, monkeypatch):
    import json

    from app.models import Outbox
    from app.telegram import cipher

    monkeypatch.setattr(settings(), "telegram_webhook_secret", SecretStr("hook-e2e"))
    human = {"id": 3300, "is_bot": False, "first_name": "Trader"}
    message = {
        "message_id": 1,
        "date": int(time.time()),
        "chat": {"id": 3300, "type": "private"},
        "from": human,
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "hook-e2e"}
    assert (
        client.post(
            "/v1/telegram/webhook",
            headers=headers,
            json={"update_id": 500, "message": {**message, "text": "/link"}},
        ).status_code
        == 200
    )
    with database.begin() as db:
        item = db.scalar(select(Outbox))
        assert "sealed" in item.body
        text = json.loads(cipher().decrypt(item.body["sealed"].encode()))["text"]
        code = text.split("Pairing code: ")[1].splitlines()[0]
    fake = FakeAgent(client)
    fake.pair(code)
    fake.execution_enabled = True
    fake.tick()
    assert (
        client.post(
            "/v1/telegram/webhook",
            headers=headers,
            json={"update_id": 501, "message": {**message, "text": "/be XAUUSD 50"}},
        ).status_code
        == 200
    )
    fake.tick()
    fake.tick()
    with database.begin() as db:
        preview = db.scalar(select(Command).where(Command.status == "AWAITING_CONFIRMATION"))
        cid = preview.id
    callback = {
        "id": "cb1",
        "from": human,
        "chat_instance": "1",
        "message": {**message, "text": "Preview"},
        "data": "confirm:" + cid,
    }
    assert (
        client.post(
            "/v1/telegram/webhook",
            headers=headers,
            json={"update_id": 502, "callback_query": callback},
        ).status_code
        == 200
    )
    fake.tick()
    fake.tick()
    with database.begin() as db:
        execution = db.scalar(select(Command).where(Command.type == "PROTECT_BREAKEVEN"))
        assert execution.status == "SUCCEEDED"
        assert (
            db.scalar(select(Result).where(Result.command_id == execution.id)).summary[
                "confirmed_volume"
            ]
            == 0.3
        )


def test_pair_rate_limit_counts_invalid_codes(client):
    fake = FakeAgent(client)
    body = {**fake.state(), "pairing_code": "AAAA-BBBB-CCCC"}
    for _ in range(10):
        assert client.post("/v1/agent/pair", json=body).status_code == 401
    assert client.post("/v1/agent/pair", json=body).status_code == 429


def test_agent_cannot_submit_other_agents_result(database, paired, client):
    user_id, fake = paired
    cid = execute(database, paired)
    with database.begin() as db:
        code = pairing_code(db, service.get_user(db, 9999))
    other = FakeAgent(client)
    other.state = lambda: {
        **fake.state(),
        "installation_id": other.credentials["installation_id"],
        "account": {**fake.state()["account"], "login": 999999},
    }
    other.pair(code)
    fake.tick()
    other.pending = fake.pending
    with pytest.raises(httpx.HTTPStatusError) as exc:
        other.tick()
    assert exc.value.response.status_code == 404
    with database.begin() as db:
        assert db.get(Command, cid).status == "LEASED"


def test_sweeper_expires_without_poll(database, paired):
    from app.maintenance import sweep_once

    cid = preview(database, paired[0])
    with database.begin() as db:
        db.get(Command, cid).expires_at = now() - timedelta(seconds=1)
    sweep_once()
    with database.begin() as db:
        assert db.get(Command, cid).status == "EXPIRED"


def test_double_confirmation_creates_one_execution(database, paired):
    if database.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    user_id, fake = paired
    cid = preview(database, user_id)
    fake.tick()
    fake.tick()

    def confirm(_):
        with database.begin() as db:
            return service.confirm(db, db.get(User, user_id), cid).id

    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(confirm, range(2)))
    assert ids[0] == ids[1]
    with database.begin() as db:
        assert (
            len(list(db.scalars(select(Command).where(Command.type == "PROTECT_BREAKEVEN")))) == 1
        )


def test_unleased_result_rejected(database, paired):
    cid = preview(database, paired[0])
    fake = paired[1]
    fake.pending = {"command_id": cid, "status": "SUCCEEDED", "summary": {}, "position_results": []}
    with pytest.raises(httpx.HTTPStatusError) as exc:
        fake.tick()
    assert exc.value.response.status_code == 409


def test_revoke_inflight_retains_block(database, paired):
    cid = execute(database, paired, "close")
    paired[1].tick()
    with database.begin() as db:
        user = db.get(User, paired[0])
        service.revoke(db, user, user.selected_account_id)
        assert db.get(Command, cid).status == "UNCERTAIN"
        assert db.get(Account, user.selected_account_id).status == "BLOCKED_UNCERTAIN"


def test_new_terminal_session_cannot_reexecute_lease(database, paired):
    import uuid

    cid = execute(database, paired, "close")
    fake = paired[1]
    fake.tick()
    original = fake.session_id
    fake.session_id = str(uuid.uuid4())
    pending = fake.pending
    fake.pending = None
    assert fake.tick()["code"] == "AGENT_SESSION_BUSY"
    with database.begin() as db:
        db.get(Agent, fake.credentials["agent_id"]).last_seen_at = now() - timedelta(seconds=11)
    reply = fake.tick()
    assert reply["code"] == "BLOCKED_UNCERTAIN" and reply["command"] is None
    with database.begin() as db:
        assert db.get(Command, cid).delivery_session_id == original
    fake.pending = pending
    fake.tick()
    with database.begin() as db:
        assert db.get(Command, cid).status == "SUCCEEDED"


def test_be_reports_partial_when_eligible_volume_is_insufficient(database, paired):
    from app.domain import D, Position

    paired[1].positions = [
        Position("1", "XAUUSD", "BUY", D(".1"), D(2390)),
        Position("2", "XAUUSD", "BUY", D(".9"), D(2420)),
    ]
    cid = execute(database, paired)
    paired[1].tick()
    paired[1].tick()
    with database.begin() as db:
        assert db.get(Command, cid).status == "PARTIAL"
        result = db.scalar(select(Result).where(Result.command_id == cid))
        assert result.summary["requested_volume"] == 0.5
        assert result.summary["confirmed_volume"] == 0.1
