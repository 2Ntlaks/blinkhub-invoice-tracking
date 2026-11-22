"""FastAPI application factory.

``uvicorn app.main:app`` uses settings from the environment. Tests call
:func:`create_app` with their own settings and a frozen clock.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.db import Clock, make_engine, make_session_factory, utc_now
from app.errors import install_error_handlers
from app.models import Base
from app.routers import catalog, dashboard, flags, invoices, meta
from app.seed import seed_if_empty

logger = logging.getLogger("blinkhub")


def create_app(settings: Settings | None = None, clock: Clock = utc_now) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.seed_on_startup:
            if seed_if_empty(engine, clock()):
                logger.info("Database was empty: loaded the case-study seed data.")
        else:
            Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="BlinkHub Invoice & Payment Tracking API",
        version="1.0.0",
        description="Prototype for the ProcureSense case study. See docs/api-contract.md.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.clock = clock

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for module in (meta, catalog, invoices, flags, dashboard):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
