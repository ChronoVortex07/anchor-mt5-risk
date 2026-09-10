from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def now():
    # UTC without offset in storage; PostgreSQL clock and all conversions use UTC.
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings().database_url, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session.begin() as db:
        yield db
