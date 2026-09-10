import asyncio
import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app import service
from app.config import settings
from app.db import Session, now, session
from app.links import EA_DOWNLOAD_URL, REPOSITORY_URL, SETUP_URL
from app.maintenance import sweep_loop
from app.models import Command, Mapping, Result, User, WebSession
from app.schemas import AliasInput, Login, Pair, Poll
from app.security import authenticate, digest, rate_limit
from app.telegram import handle_update, outbox_loop

structlog.configure(
    processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()]
)


@asynccontextmanager
async def lifespan(app):
    tasks = [asyncio.create_task(outbox_loop()), asyncio.create_task(sweep_loop())]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="MT5 Risk Agent", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None
)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data.extend(message.get("body", b""))
            if len(data) > 65536:
                await Response("PAYLOAD_TOO_LARGE", status_code=413)(scope, receive, send)
                return
            if not message.get("more_body"):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://telegram.org; "
        "frame-src https://oauth.telegram.org; img-src 'self' https: data:; "
        "style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def limit(key, count, seconds):
    # Independent committed rate accounting survives validation/auth failure.
    with Session.begin() as db:
        rate_limit(db, key, count, seconds)


def agent_auth(
    request: Request,
    authorization: str = Header(default=""),
    x_agent_id: str = Header(default=""),
    db=Depends(session),
):
    limit("agentip:" + digest(request.client.host), 600, 60)
    agent = authenticate(db, x_agent_id, authorization)
    limit("agent:" + agent.id, 180, 60)
    return agent


@app.get("/v1/config")
def public_config():
    return {
        "bot_username": settings().telegram_bot_username,
        "repository_url": REPOSITORY_URL,
        "ea_download_url": EA_DOWNLOAD_URL,
        "setup_url": SETUP_URL,
    }


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/readyz")
def ready(db=Depends(session)):
    db.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
    return {"status": "ready"}


@app.post("/v1/agent/pair")
def pair(body: Pair, request: Request, db=Depends(session)):
    limit("pair:" + digest(request.client.host), 10, 600)
    try:
        return service.pair(db, body)
    except IntegrityError:
        raise HTTPException(409, "PAIRING_CONFLICT") from None


@app.post("/v1/agent/poll")
def poll(body: Poll, agent=Depends(agent_auth), db=Depends(session)):
    return service.poll(db, agent, body)


@app.post("/v1/telegram/webhook")
def webhook(
    request: Request,
    body: dict,
    x_telegram_bot_api_secret_token: str = Header(default=""),
    db=Depends(session),
):
    expected = settings().telegram_webhook_secret.get_secret_value()
    if not expected or not hmac.compare_digest(expected, x_telegram_bot_api_secret_token):
        raise HTTPException(401, "INVALID_WEBHOOK_SECRET")
    from pydantic import ValidationError

    try:
        handle_update(db, body)
    except ValidationError:
        raise HTTPException(422, "INVALID_TELEGRAM_UPDATE") from None
    if body.get("callback_query"):
        # Telegram executes this method from the webhook response; no extra worker
        # round trip is needed to dismiss the confirmation-button spinner.
        return {"method": "answerCallbackQuery", "callback_query_id": body["callback_query"]["id"]}
    return {"ok": True}


@app.post("/v1/web/login")
def login(body: Login, request: Request, response: Response, db=Depends(session)):
    limit("login:" + digest(request.client.host), 30, 600)
    token = settings().telegram_bot_token.get_secret_value()
    if not token or not -30 <= time.time() - body.auth_date <= 300:
        raise HTTPException(401, "INVALID_TELEGRAM_LOGIN")
    fields = body.model_dump(exclude_none=True, exclude={"hash"})
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    expected = hmac.new(
        hashlib.sha256(token.encode()).digest(), check.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, body.hash):
        raise HTTPException(401, "INVALID_TELEGRAM_LOGIN")
    user = service.get_user(db, body.id, body.username)
    secret = secrets.token_urlsafe(32)
    db.add(
        WebSession(
            user_id=user.id,
            token_hash=digest(secret),
            expires_at=now() + timedelta(seconds=settings().session_seconds),
        )
    )
    response.set_cookie(
        "risk_session",
        secret,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=settings().session_seconds,
        path="/v1/web",
    )
    return {"ok": True}


def web_user(request: Request, db=Depends(session)):
    if (
        request.method not in ("GET", "HEAD")
        and request.headers.get("origin") != settings().public_url
    ):
        raise HTTPException(403, "INVALID_ORIGIN")
    token = request.cookies.get("risk_session", "")
    login = db.scalar(
        select(WebSession).where(
            WebSession.token_hash == digest(token), WebSession.expires_at > now()
        )
    )
    if not login:
        raise HTTPException(401, "LOGIN_REQUIRED")
    return db.get(User, login.user_id)


@app.get("/v1/web/accounts")
def accounts(user=Depends(web_user), db=Depends(session)):
    return service.accounts_view(db, user)


@app.get("/v1/web/history")
def history(user=Depends(web_user), db=Depends(session)):
    commands = db.scalars(
        select(Command)
        .where(Command.user_id == user.id)
        .order_by(Command.created_at.desc())
        .limit(100)
    )
    result = []
    for c in commands:
        r = db.scalar(select(Result).where(Result.command_id == c.id))
        status = c.status
        if c.expires_at <= now() and c.status in ("PENDING", "AWAITING_CONFIRMATION"):
            status = "EXPIRED"
        elif c.expires_at <= now() and c.status == "LEASED":
            status = "UNCERTAIN" if c.type in service.EXECUTIONS else "EXPIRED"
        result.append(
            {
                "id": c.id,
                "account_id": c.account_id,
                "type": c.type,
                "status": status,
                "created_at": c.created_at.isoformat() + "Z",
                "payload": c.payload,
                "summary": r.summary if r else None,
            }
        )
    return result


@app.post("/v1/web/accounts/{account_id}/select")
def select_account(account_id: str, user=Depends(web_user), db=Depends(session)):
    service.owned_account(db, user, account_id)
    user.selected_account_id = account_id
    return {"ok": True}


@app.post("/v1/web/accounts/{account_id}/revoke")
def revoke(account_id: str, user=Depends(web_user), db=Depends(session)):
    service.revoke(db, user, account_id)
    return {"ok": True}


@app.put("/v1/web/accounts/{account_id}/mappings")
def mapping(account_id: str, body: AliasInput, user=Depends(web_user), db=Depends(session)):
    service.owned_account(db, user, account_id, lock=True)
    item = db.scalar(
        select(Mapping).where(Mapping.account_id == account_id, Mapping.alias == body.alias.lower())
    )
    if not item:
        item = Mapping(
            account_id=account_id, alias=body.alias.lower(), actual_symbol=body.actual_symbol
        )
        db.add(item)
    else:
        item.actual_symbol = body.actual_symbol
    service.audit(
        db, "SYMBOL_MAPPING_SET", user_id=user.id, account_id=account_id, details=body.model_dump()
    )
    return {"ok": True}


# Built frontend is copied here by the multi-stage image. API routes take precedence.
from pathlib import Path  # noqa: E402

if Path("static").is_dir():
    app.mount("/", StaticFiles(directory="static", html=True), name="dashboard")
