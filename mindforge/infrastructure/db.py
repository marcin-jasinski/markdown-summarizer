"""
Database engine factory and migration runner.

No module-level engine is created here — callers must invoke
`create_async_engine()` exactly once at the composition root.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine as _sa_create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool


def create_async_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """
    Return a configured SQLAlchemy `AsyncEngine`.

    Pool defaults are intentionally conservative for the expected single-server
    deployment (1–5 concurrent users).  Tune via environment if needed.
    """
    return _sa_create_async_engine(
        database_url,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,  # recycle connections after 1 hour
        pool_pre_ping=True,  # verify connection liveness before use
        echo=echo,
    )


async def run_migrations(conn: AsyncConnection) -> None:
    """
    Run Alembic migrations programmatically using the provided connection.

    Call this inside the lifespan handler after creating the engine so that
    migrations always complete before the application starts serving requests.
    """
    from alembic import command
    from alembic.config import Config

    def _run_sync(sync_conn):  # type: ignore[no-untyped-def]
        cfg = Config("migrations/alembic.ini")
        cfg.attributes["connection"] = sync_conn
        command.upgrade(cfg, "head")

    await conn.run_sync(_run_sync)
