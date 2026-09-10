import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from app import db, main, maintenance, service, telegram  # noqa: E402
from app.db import Base  # noqa: E402
from app.security import pairing_code  # noqa: E402
from fake_agent import FakeAgent  # noqa: E402


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    if url != "sqlite://" and not url.endswith("/risk_test"):
        raise RuntimeError("Tests may only reset the dedicated risk_test database")
    opts = (
        {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        if url == "sqlite://"
        else {}
    )
    engine = create_engine(url, **opts)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "Session", factory)
    monkeypatch.setattr(main, "Session", factory)
    monkeypatch.setattr(telegram, "Session", factory)
    monkeypatch.setattr(maintenance, "Session", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client(database):
    # No lifespan: no Telegram network calls are made by tests.
    return TestClient(main.app, base_url="https://testserver")


@pytest.fixture
def paired(database, client):
    with database.begin() as s:
        user = service.get_user(s, 1001)
        code = pairing_code(s, user)
        user_id = user.id
    agent = FakeAgent(client)
    agent.pair(code)
    agent.execution_enabled = True
    agent.tick()
    return user_id, agent
