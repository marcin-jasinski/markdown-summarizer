"""
Shared fixtures for integration tests against a real PostgreSQL database.

Requires a running Postgres instance (set TEST_DATABASE_URL or use the
testcontainers fixture).  These tests are skipped automatically when the
database is not available.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mindforge.infrastructure.persistence.models import Base

# ---------------------------------------------------------------------------
# Database URL resolution
# ---------------------------------------------------------------------------


def _test_db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge_test",
    )


# ---------------------------------------------------------------------------
# Engine + schema fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def engine():
    url = _test_db_url()
    eng = create_async_engine(url, echo=False)
    try:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()  # roll back after each test for isolation
