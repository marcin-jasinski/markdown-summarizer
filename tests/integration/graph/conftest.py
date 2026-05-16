"""Integration tests for the Neo4j graph layer.

These tests require a running Neo4j instance.  Set ``TEST_NEO4J_URI``,
``TEST_NEO4J_PASSWORD``, and optionally ``TEST_NEO4J_DATABASE`` in the
environment, or start Neo4j via Docker Compose.

Tests are automatically skipped when Neo4j is unreachable.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _neo4j_uri() -> str:
    return os.environ.get("TEST_NEO4J_URI", "bolt://localhost:7687")


def _neo4j_password() -> str:
    return os.environ.get("TEST_NEO4J_PASSWORD", "password")


def _neo4j_database() -> str:
    return os.environ.get("TEST_NEO4J_DATABASE", "neo4j")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def neo4j_ctx():
    """Session-scoped Neo4jContext; skips if Neo4j is unreachable."""
    try:
        from mindforge.infrastructure.graph.neo4j_context import Neo4jContext
    except ImportError:
        pytest.skip("neo4j package not installed")

    ctx = Neo4jContext(
        uri=_neo4j_uri(),
        password=_neo4j_password(),
        database=_neo4j_database(),
    )
    try:
        await ctx.verify_connectivity()
        await ctx.ensure_schema()
    except Exception as exc:
        await ctx.close()
        pytest.skip(f"Neo4j unreachable: {exc}")

    yield ctx
    await ctx.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_graph(neo4j_ctx):
    """Wipe the test database before each test for isolation."""
    async with neo4j_ctx.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    # post-test cleanup is handled by the next test's pre-test wipe
