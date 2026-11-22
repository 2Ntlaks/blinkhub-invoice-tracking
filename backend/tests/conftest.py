"""Shared test fixtures: a freshly seeded app on a throwaway SQLite file, with time frozen."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

#: Frozen "now" for API tests, so seeded ages are exactly the case-study numbers.
FROZEN_NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)

FINANCE = {"X-User-Id": "1"}
MANAGER = {"X-User-Id": "2"}
UBUNTU = {"X-User-Id": "3"}  # supplier 1, Ubuntu Cleaning (SMME)
PRIME = {"X-User-Id": "4"}  # supplier 2, Prime Facilities
THUTO = {"X-User-Id": "5"}  # supplier 3, Thuto Supplies
SISONKE = {"X-User-Id": "10"}  # supplier 8, Sisonke Trading (INACTIVE)


class Clock:
    """A clock tests can move forward."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock(FROZEN_NOW)


@pytest.fixture
def client(tmp_path, clock):
    """A new database for every test, so tests can change data without affecting each other."""
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", seed_on_startup=True)
    with TestClient(create_app(settings, clock=clock)) as test_client:
        yield test_client
