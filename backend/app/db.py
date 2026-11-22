"""Database engine and sessions.

``DATABASE_URL`` picks the database: a SQLite file by default (no Docker on the dev
machine), PostgreSQL under Docker Compose. Only portable SQLAlchemy types are used,
so the same models work on both.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Current time in UTC, to the second (the contract's timestamps have no fractions)."""
    return datetime.now(UTC).replace(microsecond=0)


def make_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # FastAPI may run a request on a different thread from the one that opened the
        # connection; SQLite refuses that unless told it is fine.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: after a commit we still build the response from the
    # objects we already hold, without a surprise reload.
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
