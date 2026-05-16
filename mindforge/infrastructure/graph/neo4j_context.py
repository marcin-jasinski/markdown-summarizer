"""Neo4j async driver context — manages the AsyncDriver lifecycle.

This module is the single point of Neo4j connection creation.  All other graph
modules receive a ``Neo4jContext`` instance via dependency injection from the
composition root; they never call ``neo4j.AsyncGraphDatabase`` directly.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

try:
    from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
    from neo4j.exceptions import Neo4jError, ServiceUnavailable
except ImportError:
    AsyncDriver = None  # type: ignore[assignment,misc]
    AsyncGraphDatabase = None  # type: ignore[assignment]
    AsyncSession = None  # type: ignore[assignment,misc]
    Neo4jError = Exception  # type: ignore[assignment,misc]
    ServiceUnavailable = Exception  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)


class Neo4jContext:
    """Wraps an ``AsyncDriver`` and exposes a session context manager.

    Usage::

        ctx = Neo4jContext(uri="bolt://localhost:7687",
                           password="secret",
                           database="neo4j")
        await ctx.verify_connectivity()
        async with ctx.session() as session:
            await session.run("RETURN 1")
        await ctx.close()
    """

    def __init__(
        self,
        uri: str,
        password: str,
        database: str = "neo4j",
        username: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: float = 30.0,
    ) -> None:
        if AsyncGraphDatabase is None:
            raise ImportError(
                "neo4j package is not installed. "
                "Add 'neo4j' to your dependencies to use the graph layer."
            )
        self._database = database
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri,
            auth=(username, password),
            max_connection_pool_size=max_connection_pool_size,
            connection_timeout=connection_timeout,
        )
        log.info("Neo4jContext: driver created for %s (db=%s)", uri, database)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a Neo4j async session scoped to the configured database."""
        async with self._driver.session(database=self._database) as sess:
            yield sess

    async def verify_connectivity(self) -> None:
        """Raise ``ServiceUnavailable`` if Neo4j cannot be reached."""
        await self._driver.verify_connectivity()
        log.info("Neo4jContext: connectivity verified")

    async def ensure_schema(self, *, embedding_dimensions: int = 1536) -> None:
        """Create uniqueness constraints and search indexes if they do not exist.

        DDL statements must run in auto-commit (implicit) transactions in Neo4j,
        so each statement is executed individually via ``session.run()``.
        Safe to call on every startup thanks to the ``IF NOT EXISTS`` guards.
        """
        from mindforge.infrastructure.graph.cypher_queries import (
            CREATE_CONSTRAINTS,
            CREATE_FULLTEXT_INDEX,
            CREATE_VECTOR_INDEX,
        )

        async with self.session() as session:
            # Constraints — split on ';' because the constant holds multiple DDL stmts
            for stmt in CREATE_CONSTRAINTS.split(";"):
                stmt = stmt.strip()
                if stmt:
                    await session.run(stmt)

            await session.run(CREATE_FULLTEXT_INDEX.rstrip(";"))
            await session.run(
                CREATE_VECTOR_INDEX.rstrip(";"),
                dimensions=embedding_dimensions,
            )

        log.info(
            "Neo4jContext: schema ensured (constraints + indexes, dimensions=%d)",
            embedding_dimensions,
        )

    async def close(self) -> None:
        """Close the driver and release all pooled connections."""
        await self._driver.close()
        log.info("Neo4jContext: driver closed")
