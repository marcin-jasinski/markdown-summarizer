"""
FastAPI application factory and composition root.

The single composition root lives in :func:`lifespan` — every shared object
(DB engine, gateway, repos, session stores) is created once here and attached
to ``app.state``.  No module-level singletons are used.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mindforge.api.middleware import add_middleware
from mindforge.infrastructure.config import (
    AppSettings,
    validate_settings,
)

log = logging.getLogger(__name__)


def _configure_app_logging(level_name: str) -> None:
    """Ensure MindForge application logs are always emitted to container stdout."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    app_log = logging.getLogger("mindforge")
    app_log.setLevel(level)
    app_log.propagate = False

    for handler in app_log.handlers:
        if getattr(handler, "_mindforge_managed", False):
            return

    handler = logging.StreamHandler()
    handler._mindforge_managed = True  # type: ignore[attr-defined]
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    app_log.addHandler(handler)


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized API exception handlers with consistent logging."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        if exc.status_code >= 500:
            log.error(
                "HTTP %s during %s %s [request_id=%s]",
                exc.status_code,
                request.method,
                request.url.path,
                request_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        log.exception(
            "Unhandled exception during %s %s [request_id=%s]",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Wewnętrzny błąd serwera."},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Composition root — runs once on startup, tears down on shutdown."""

    # 1. Load and validate settings
    settings = AppSettings()
    validate_settings(settings)
    app.state.settings = settings
    _configure_app_logging(settings.log_level)

    # 2. Database engine + session factory
    from mindforge.infrastructure.db import create_async_engine, run_migrations
    from sqlalchemy import text

    engine = create_async_engine(settings.database_url)
    app.state.db_engine = engine
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    app.state.session_factory = session_factory

    # 3. Run Alembic migrations with advisory lock to prevent concurrent upgrades
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(1234567890)"))
            await run_migrations(conn)
    except Exception as exc:
        log.warning("Migration step failed or skipped: %s", exc)

    # 4. Neo4j context (optional — requires enable_graph)
    neo4j_context = None
    if settings.enable_graph:
        try:
            from mindforge.infrastructure.graph.neo4j_context import Neo4jContext

            neo4j_context = Neo4jContext(
                uri=settings.neo4j_uri,
                password=settings.neo4j_password,
                database=settings.neo4j_database,
                username=settings.neo4j_username,
            )
            await neo4j_context.verify_connectivity()
            log.info("Neo4j connected: %s", settings.neo4j_uri)
        except Exception as exc:
            log.warning("Neo4j unavailable — graph features disabled: %s", exc)
            neo4j_context = None
    app.state.neo4j_context = neo4j_context

    # 5. AI Gateway
    from mindforge.infrastructure.ai.infra.gateway import LiteLLMGateway

    gateway = LiteLLMGateway(
        default_model=settings.model_small,
        model_map=settings.model_map,
        fallback_models=[settings.model_fallback],
        timeout_seconds=30.0,
        max_retries=3,
        api_key=settings.openrouter_api_key,
    )
    app.state.gateway = gateway

    # 6. Redis (optional — fallback to PostgreSQL when absent)
    redis_client = None
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            log.info("Redis connected: %s", settings.redis_url)
        except Exception as exc:
            log.warning(
                "Redis unavailable — quiz sessions and SSE will use PostgreSQL fallback: %s",
                exc,
            )
            redis_client = None
    app.state.redis_client = redis_client

    # 7. Outbox relay — always started; redis_client=None activates log-only
    # degraded mode so unpublished outbox rows don't accumulate indefinitely.
    try:
        from mindforge.infrastructure.events.outbox_relay import OutboxRelay

        outbox_relay = OutboxRelay(engine=engine, redis_client=redis_client)
        await outbox_relay.start()
        log.info("Outbox relay started (redis=%s)", redis_client is not None)
    except Exception as exc:
        outbox_relay = None
        log.warning("Outbox relay failed to start: %s", exc)
    app.state.outbox_relay = outbox_relay

    # 8. Retrieval adapter
    retrieval = None
    if neo4j_context is not None:
        try:
            from mindforge.infrastructure.graph.neo4j_retrieval import (
                Neo4jRetrievalAdapter,
            )

            retrieval = Neo4jRetrievalAdapter(context=neo4j_context)
        except Exception as exc:
            log.warning("Retrieval adapter init failed: %s", exc)
    app.state.retrieval = retrieval

    # 8a. Pre-load chat prompt strings once (I/O at startup, never at request time)
    from mindforge.infrastructure.ai.agents import chat as _chat_prompts

    app.state.chat_system_with_context = _chat_prompts.SYSTEM_WITH_CONTEXT
    app.state.chat_system_no_context = _chat_prompts.SYSTEM_NO_CONTEXT

    # 8b. Shared in-memory chat session cache (used when Redis is absent).
    # Must be a singleton so sessions created in one request are visible in
    # subsequent requests on the same worker process.
    from mindforge.application.chat import _InMemorySessionCache

    app.state.chat_memory_cache = _InMemorySessionCache(
        ttl_seconds=settings.quiz_session_ttl_seconds
    )

    # 9. Quiz session store (Redis preferred, PostgreSQL fallback)
    app.state.quiz_session_store = _make_quiz_store(
        settings, redis_client, session_factory
    )

    # 10. Parser registry
    from mindforge.infrastructure.parsing.registry import ParserRegistry
    from mindforge.infrastructure.parsing.markdown_parser import MarkdownParser
    from mindforge.infrastructure.parsing.pdf_parser import PdfParser
    from mindforge.infrastructure.parsing.docx_parser import DocxParser
    from mindforge.infrastructure.parsing.txt_parser import TxtParser

    parser_registry = ParserRegistry()
    parser_registry.register("text/markdown", MarkdownParser())
    parser_registry.register("text/x-markdown", MarkdownParser())
    parser_registry.register("application/pdf", PdfParser())
    parser_registry.register(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DocxParser(),
    )
    parser_registry.register("application/msword", DocxParser())
    parser_registry.register("text/plain", TxtParser())
    app.state.parser_registry = parser_registry

    # 11. JWT service
    from mindforge.api.auth import make_jwt_service

    app.state.jwt_service = make_jwt_service(settings)

    # 12. Durable event consumers
    # GraphIndexerConsumer rebuilds Neo4j from ProcessingCompleted events.
    # AuditLoggerConsumer writes auditable events to interaction_turns.
    # Both poll outbox_events directly via cursor — no Redis dependency.
    from mindforge.infrastructure.events.durable_consumer import (
        AuditLoggerConsumer,
        GraphIndexerConsumer,
    )
    from mindforge.infrastructure.persistence.artifact_repo import (
        PostgresArtifactRepository,
    )
    from mindforge.infrastructure.persistence.interaction_repo import (
        PostgresInteractionStore,
    )

    consumers: list = []
    if neo4j_context is not None:
        try:
            from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

            graph_indexer = Neo4jGraphIndexer(neo4j_context)
            graph_consumer = GraphIndexerConsumer(
                engine=engine,
                graph_indexer=graph_indexer,
                artifact_repo_factory=lambda s: PostgresArtifactRepository(s),
            )
            await graph_consumer.start()
            consumers.append(graph_consumer)
            log.info("GraphIndexerConsumer started")
        except Exception as exc:
            log.warning("GraphIndexerConsumer failed to start: %s", exc)

    try:
        audit_consumer = AuditLoggerConsumer(
            engine=engine,
            interaction_repo_factory=lambda s: PostgresInteractionStore(s),
        )
        await audit_consumer.start()
        consumers.append(audit_consumer)
        log.info("AuditLoggerConsumer started")
    except Exception as exc:
        log.warning("AuditLoggerConsumer failed to start: %s", exc)

    app.state.consumers = consumers

    # 13. Quiz agents — constructed once at startup and injected per-request
    from mindforge.agents.quiz_generator import QuizGeneratorAgent
    from mindforge.agents.quiz_evaluator import QuizEvaluatorAgent
    from mindforge.infrastructure.ai.agents import quiz_generator as _qg_prompts
    from mindforge.infrastructure.ai.agents import quiz_evaluator as _qe_prompts

    app.state.quiz_generator = QuizGeneratorAgent(prompts=_qg_prompts)
    app.state.quiz_evaluator = QuizEvaluatorAgent(prompts=_qe_prompts)

    log.info("MindForge API started — all dependencies wired.")

    yield

    # --- Teardown ---
    for consumer in getattr(app.state, "consumers", []):
        await consumer.stop()
    if outbox_relay is not None:
        await outbox_relay.stop()
    if neo4j_context is not None:
        await neo4j_context.close()
    if redis_client is not None:
        await redis_client.aclose()
    await engine.dispose()
    log.info("MindForge API shut down cleanly.")


def _make_quiz_store(settings: AppSettings, redis_client, session_factory):
    """Build quiz session store — Redis preferred, PG fallback."""
    if redis_client is not None:
        try:
            from mindforge.infrastructure.cache.redis_quiz_sessions import (
                RedisQuizSessionStore,
            )

            return RedisQuizSessionStore(
                redis_client=redis_client,
                ttl_seconds=settings.quiz_session_ttl_seconds,
            )
        except Exception as exc:
            log.warning("Redis quiz session store init failed: %s", exc)

    try:
        from mindforge.infrastructure.persistence.pg_quiz_sessions import (
            PostgresQuizSessionStore,
        )

        return PostgresQuizSessionStore(session_factory=session_factory)
    except Exception:
        from mindforge.infrastructure.cache.memory_quiz_sessions import (
            InMemoryQuizSessionStore,
        )

        log.warning("Using in-memory quiz session store — sessions lost on restart.")
        return InMemoryQuizSessionStore()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MindForge API",
        description="Knowledge management and AI tutoring platform.",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    register_exception_handlers(app)

    # Register middleware
    add_middleware(app)

    # Register routers
    from mindforge.api.routers import (
        health,
        auth,
        knowledge_bases,
        documents,
        concepts,
        quiz,
        flashcards,
        search,
        chat,
        events,
        tasks,
        interactions,
        admin,
        users,
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(knowledge_bases.router)
    app.include_router(documents.router)
    app.include_router(concepts.router)
    app.include_router(quiz.router)
    app.include_router(flashcards.router)
    app.include_router(search.router)
    app.include_router(chat.router)
    app.include_router(events.router)
    app.include_router(tasks.router)
    app.include_router(interactions.router)
    app.include_router(admin.router)
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

    # Serve Angular SPA (only if built)
    spa_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "dist", "frontend", "browser"
    )
    if os.path.isdir(spa_path):
        app.mount("/", StaticFiles(directory=spa_path, html=True), name="spa")

    return app


# Module-level app instance used by uvicorn
app = create_app()


def run() -> None:
    """Entry point for the ``mindforge-api`` CLI command."""
    uvicorn.run(
        "mindforge.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
