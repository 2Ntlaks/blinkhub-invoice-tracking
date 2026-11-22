"""Settings read from environment variables (contract section 6)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.rules import PAYMENT_TERMS_DAYS

DEFAULT_DATABASE_URL = "sqlite:///./blinkhub.db"
DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    seed_on_startup: bool = True
    cors_origins: list[str] = field(default_factory=lambda: [DEFAULT_CORS_ORIGINS])
    # Re-exported from rules so the dashboard can report the value it was computed with.
    payment_terms_days: int = PAYMENT_TERMS_DAYS

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
        return cls(
            database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
            seed_on_startup=_env_bool("SEED_ON_STARTUP", True),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        )
