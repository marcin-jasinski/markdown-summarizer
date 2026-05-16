"""
Pipeline worker — CLI entry point for the document processing background process.

Polls ``pipeline_tasks`` using ``SELECT … FOR UPDATE SKIP LOCKED`` so that
multiple worker processes can run safely in parallel without stepping on each
other.

Lifecycle:
  1. On startup: recover stale tasks (status='running', claimed_at too old).
  2. Loop: claim pending task → execute → mark done/failed.
  3. On SIGTERM: stop accepting new tasks and drain in-flight work.

Composition root: ``main()`` wires all dependencies from ``AppSettings`` and
creates the single ``AsyncEngine``.  No module-level singletons anywhere.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mindforge.agents import AgentRegistry
from mindforge.agents.article_fetcher import ArticleFetcherAgent
from mindforge.agents.concept_mapper import ConceptMapperAgent
from mindforge.agents.flashcard_generator import FlashcardGeneratorAgent
from mindforge.agents.image_analyzer import ImageAnalyzerAgent
from mindforge.agents.preprocessor import PreprocessorAgent
from mindforge.agents.relevance_guard import RelevanceGuardAgent
from mindforge.agents.summarizer import SummarizerAgent
from mindforge.application.orchestration import OrchestrationGraph
from mindforge.application.pipeline import PipelineOrchestrator, StepExecutionError
from mindforge.domain.agents import AgentContext, ProcessingSettings
from dataclasses import replace as _dc_replace
from mindforge.domain.models import DocumentArtifact
from mindforge.domain.ports import AIGateway, ArtifactRepository
from mindforge.infrastructure.ai.infra.gateway import LiteLLMGateway
from mindforge.infrastructure.config import AppSettings, load_egress_settings
from mindforge.infrastructure.db import create_async_engine
from mindforge.infrastructure.events import OutboxEventPublisher
from mindforge.infrastructure.events.outbox_publisher import notify_outbox
from mindforge.infrastructure.events.outbox_relay import (
    OutboxRelay,
    purge_published_events,
)
from mindforge.infrastructure.graph.neo4j_context import Neo4jContext
from mindforge.infrastructure.graph.neo4j_retrieval import Neo4jRetrievalAdapter
from mindforge.infrastructure.security.egress_policy import EgressPolicy
from mindforge.infrastructure.ai.agents import (
    preprocessor as _preprocessor_prompts,
    summarizer as _summarizer_prompts,
    image_analyzer as _image_analyzer_prompts,
    relevance_guard as _relevance_guard_prompts,
    article_fetcher as _article_fetcher_prompts,
    flashcard_gen as _flashcard_gen_prompts,
    concept_mapper as _concept_mapper_prompts,
)
from mindforge.infrastructure.persistence.artifact_repo import (
    PostgresArtifactRepository,
)
from mindforge.infrastructure.persistence.document_repo import (
    PostgresDocumentRepository,
)
from mindforge.infrastructure.persistence.interaction_repo import (
    PostgresInteractionStore as PostgresInteractionRepository,
)
from mindforge.infrastructure.persistence.models import (
    DocumentModel,
    KnowledgeBaseModel,
    PipelineTaskModel,
)

logger = logging.getLogger(__name__)

# Maximum number of times a task can be reclaimed before being permanently failed
_MAX_RECLAIM_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# PipelineWorker
# ---------------------------------------------------------------------------


class PipelineWorker:
    """Long-running worker that consumes ``pipeline_tasks`` rows.

    All dependencies are injected; the worker itself is I/O-free at class
    definition time.

    Args:
        worker_id:      Unique string identifying this worker process
                        (used for the ``worker_id`` column in ``pipeline_tasks``).
        engine:         SQLAlchemy :class:`~sqlalchemy.ext.asyncio.AsyncEngine`.
        registry:       :class:`~mindforge.agents.AgentRegistry` with all
                        registered agent implementations.
        graph:          :class:`~mindforge.application.orchestration.OrchestrationGraph`
                        defining the pipeline DAG.
        gateway:        :class:`~mindforge.domain.ports.AIGateway` passed into
                        every :class:`~mindforge.domain.agents.AgentContext`.
        settings:       :class:`~mindforge.domain.agents.ProcessingSettings`
                        derived from ``AppSettings``.
        retrieval:      Retrieval port implementation (stub until Phase 11).
        max_concurrent: Maximum number of tasks to execute in parallel.
        poll_interval:  Seconds between poll cycles when the queue is empty.
        stale_threshold_minutes: Tasks whose ``claimed_at`` is older than this
                        are considered stale and reclaimed on startup.
    """

    def __init__(
        self,
        *,
        worker_id: str,
        engine: AsyncEngine,
        registry: AgentRegistry,
        graph: OrchestrationGraph,
        gateway: AIGateway,
        settings: ProcessingSettings,
        retrieval: Any,
        max_concurrent: int = 2,
        poll_interval: float = 2.0,
        stale_threshold_minutes: int = 30,
    ) -> None:
        self._worker_id = worker_id
        self._engine = engine
        self._registry = registry
        self._graph = graph
        self._gateway = gateway
        self._settings = settings
        self._retrieval = retrieval
        self._max_concurrent = max_concurrent
        self._poll_interval = poll_interval
        self._stale_threshold = timedelta(minutes=stale_threshold_minutes)

        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Start the worker loop.

        Runs until :meth:`shutdown` is called or the process receives
        ``SIGTERM``/``SIGINT``.
        """
        self._running = True
        logger.info(
            "PipelineWorker %r starting (max_concurrent=%d)",
            self._worker_id,
            self._max_concurrent,
        )

        await self._recover_stale_tasks()

        while self._running:
            # Respect the concurrency cap without busy-waiting
            if len(self._active_tasks) >= self._max_concurrent:
                await asyncio.sleep(self._poll_interval)
                continue

            task_row = await self._claim_task()
            if task_row is None:
                # Nothing pending — wait before polling again
                await asyncio.sleep(self._poll_interval)
                continue

            async def _run(t: PipelineTaskModel) -> None:
                async with self._semaphore:
                    await self._execute_task(t)

            at = asyncio.create_task(_run(task_row))
            self._active_tasks.add(at)
            at.add_done_callback(self._active_tasks.discard)

        # Drain in-flight tasks
        if self._active_tasks:
            logger.info(
                "Draining %d in-flight tasks…",
                len(self._active_tasks),
            )
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        logger.info("PipelineWorker %r stopped.", self._worker_id)

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        """Signal the worker to stop accepting new tasks.

        Waits up to *timeout_seconds* for in-flight tasks to complete.
        """
        logger.info("Shutdown requested for worker %r", self._worker_id)
        self._running = False
        if self._active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Graceful drain timed out after %.0fs; %d tasks still running.",
                    timeout_seconds,
                    len(self._active_tasks),
                )

    # ------------------------------------------------------------------
    # Task claim
    # ------------------------------------------------------------------

    async def _claim_task(self) -> PipelineTaskModel | None:
        """Atomically claim one pending task using ``SELECT … FOR UPDATE SKIP LOCKED``.

        Returns ``None`` if no pending task is available.
        """
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(PipelineTaskModel)
                .where(PipelineTaskModel.status == "pending")
                .order_by(PipelineTaskModel.submitted_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None

            now = datetime.now(timezone.utc)
            row.status = "running"
            row.worker_id = self._worker_id
            row.claimed_at = now
            row.started_at = now
            await session.flush()

            # Detach from session so we can use it from a fresh session later
            session.expunge(row)
            return row

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _execute_task(self, task: PipelineTaskModel) -> None:
        """Load the document and artifact, build the context, and run the
        orchestrator.  Marks the task as ``done`` or ``failed`` when finished.

        A fresh set of repositories and a fresh :class:`PipelineOrchestrator`
        are created for each task so that concurrent executions never share
        session state.  All database writes for a single task (artifact
        checkpoints, outbox events, document status, task status) are
        committed within the same session transaction.
        """
        task_id: uuid.UUID = task.task_id
        document_id: uuid.UUID = task.document_id
        logger.info("Executing task %s for document %s", task_id, document_id)

        async with self._session_factory() as session, session.begin():
            # Build per-task repos and orchestrator — no shared session state.
            artifact_repo = PostgresArtifactRepository(session)
            document_repo = PostgresDocumentRepository(session)
            interaction_repo = PostgresInteractionRepository(session)
            publisher = OutboxEventPublisher(session)

            orchestrator = PipelineOrchestrator(
                registry=self._registry,
                graph=self._graph,
                artifact_repo=artifact_repo,
                event_publisher=publisher,
                interaction_store=interaction_repo,
                document_repo=document_repo,
            )

            doc_row = await session.get(DocumentModel, document_id)
            if doc_row is None:
                logger.error(
                    "Task %s: document %s not found — marking failed",
                    task_id,
                    document_id,
                )
                await self._mark_failed(task_id, "Document not found", session=session)
                return

            artifact = await self._load_or_create_artifact(artifact_repo, doc_row)

            kb_row = await session.get(KnowledgeBaseModel, doc_row.kb_id)
            prompt_locale = kb_row.prompt_locale if kb_row is not None else "pl"
            task_settings = _dc_replace(self._settings, prompt_locale=prompt_locale)

            context = AgentContext(
                document_id=document_id,
                knowledge_base_id=doc_row.kb_id,
                artifact=artifact,
                gateway=self._gateway,
                retrieval=self._retrieval,
                settings=task_settings,
                metadata={"original_content": doc_row.original_content},
            )

            try:
                await orchestrator.run(
                    document_id=document_id,
                    artifact=artifact,
                    context=context,
                )
            except StepExecutionError as exc:
                logger.error(
                    "Task %s failed at step %r: %s", task_id, exc.step, exc.reason
                )
                await self._mark_failed(task_id, exc.reason, session=session)
                return
            except Exception as exc:
                logger.exception("Task %s raised unexpected error", task_id)
                await self._mark_failed(task_id, str(exc), session=session)
                return

            await self._mark_done(task_id, session=session)
            logger.info("Task %s completed successfully", task_id)

        # Wake OutboxRelay immediately after commit so consumers see the event
        # without waiting for the next poll interval.  Non-critical: relay falls
        # back to polling if this call fails.
        try:
            async with self._engine.begin() as notify_conn:
                await notify_outbox(notify_conn)
        except Exception:
            logger.debug("pg_notify('outbox') failed (non-critical)", exc_info=True)

    async def _load_or_create_artifact(
        self, artifact_repo: ArtifactRepository, doc_row: DocumentModel
    ) -> DocumentArtifact:
        """Return the latest stored artifact for this document, or create a fresh one."""
        existing = await artifact_repo.load_latest(doc_row.document_id)
        if existing is not None:
            return existing
        return DocumentArtifact(
            document_id=doc_row.document_id,
            knowledge_base_id=doc_row.kb_id,
            lesson_id=doc_row.lesson_id,
            version=1,
            created_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    async def _mark_done(self, task_id: uuid.UUID, *, session: AsyncSession) -> None:
        await session.execute(
            update(PipelineTaskModel)
            .where(PipelineTaskModel.task_id == task_id)
            .values(status="done", completed_at=datetime.now(timezone.utc))
        )

    async def _mark_failed(
        self,
        task_id: uuid.UUID,
        reason: str,
        *,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            update(PipelineTaskModel)
            .where(PipelineTaskModel.task_id == task_id)
            .values(
                status="failed",
                error=reason[:2000],
                completed_at=datetime.now(timezone.utc),
            )
        )

    # ------------------------------------------------------------------
    # Stale task recovery
    # ------------------------------------------------------------------

    async def _recover_stale_tasks(self) -> None:
        """On startup, reclaim tasks that a previous worker died holding.

        Tasks with ``status='running'`` and ``claimed_at`` older than
        ``stale_threshold`` are reset to ``pending`` (if reclaim_count < 3)
        or permanently failed.
        """
        cutoff = datetime.now(timezone.utc) - self._stale_threshold

        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(PipelineTaskModel)
                .where(
                    PipelineTaskModel.status == "running",
                    PipelineTaskModel.claimed_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            )
            stale = result.scalars().all()

            for row in stale:
                reclaim_count = _parse_reclaim_count(row.error)
                if reclaim_count >= _MAX_RECLAIM_ATTEMPTS:
                    logger.warning(
                        "Stale task %s exceeded max reclaim attempts — failing permanently",
                        row.task_id,
                    )
                    row.status = "failed"
                    row.error = (
                        f"[reclaim:{reclaim_count}] Exceeded max reclaim attempts"
                    )
                    row.completed_at = datetime.now(timezone.utc)
                else:
                    logger.info(
                        "Reclaiming stale task %s (reclaim_count=%d)",
                        row.task_id,
                        reclaim_count + 1,
                    )
                    row.status = "pending"
                    row.worker_id = None
                    row.claimed_at = None
                    row.started_at = None
                    row.error = (
                        f"[reclaim:{reclaim_count + 1}] Reclaimed after stale detection"
                    )

        if stale:
            logger.info("Stale task recovery: processed %d task(s)", len(stale))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubRetrieval:
    """Phase 5–6 placeholder for the RetrievalPort.

    Phase 7 (Neo4j graph layer) replaces this with a real ``Neo4jRetrievalAdapter``
    wired at composition-root time.  Until then, every retrieval call returns an
    empty result, which causes ``RelevanceGuardAgent`` to unconditionally accept
    all documents (empty-KB path).
    """

    async def retrieve(self, *a: object, **kw: object) -> list:
        return []

    async def retrieve_concept_neighborhood(self, *a: object, **kw: object) -> None:
        return None

    async def find_weak_concepts(self, *a: object, **kw: object) -> list:
        return []

    async def get_concepts(self, *a: object, **kw: object) -> list:
        return []

    async def get_lesson_concepts(self, *a: object, **kw: object) -> list:
        return []


def _parse_reclaim_count(error: str | None) -> int:
    """Extract the ``[reclaim:N]`` counter embedded in the error field."""
    if not error:
        return 0
    match = re.search(r"\[reclaim:(\d+)\]", error)
    return int(match.group(1)) if match else 0


def _make_worker_id() -> str:
    """Return a unique worker identifier combining hostname and PID."""
    return f"{socket.gethostname()}-{os.getpid()}"


# ---------------------------------------------------------------------------
# Composition root
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``mindforge-pipeline`` CLI command.

    Wires all dependencies from environment / ``.env``, then runs the
    worker loop until ``SIGTERM`` or ``SIGINT``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    async def _run() -> None:
        settings = AppSettings()
        engine = create_async_engine(settings.database_url)

        gateway = LiteLLMGateway(
            default_model=settings.model_large,
            model_map=settings.model_map,
            fallback_models=[settings.model_fallback],
            timeout_seconds=300,
            max_retries=3,
            api_key=settings.openrouter_api_key,
        )

        processing_settings = ProcessingSettings(
            chunk_max_tokens=settings.chunk_max_tokens,
            chunk_min_tokens=settings.chunk_min_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
            enable_graph=settings.enable_graph,
            enable_image_analysis=settings.enable_image_analysis,
            enable_article_fetch=settings.enable_article_fetch,
            model_tier_map=settings.model_map,
        )

        egress_settings = load_egress_settings(settings)
        egress_policy = EgressPolicy(egress_settings)

        registry = AgentRegistry()
        registry.register(PreprocessorAgent(prompts=_preprocessor_prompts))
        registry.register(ImageAnalyzerAgent(prompts=_image_analyzer_prompts))
        registry.register(RelevanceGuardAgent(prompts=_relevance_guard_prompts))
        registry.register(
            ArticleFetcherAgent(
                egress_policy=egress_policy, prompts=_article_fetcher_prompts
            )
        )
        registry.register(SummarizerAgent(prompts=_summarizer_prompts))
        registry.register(FlashcardGeneratorAgent(prompts=_flashcard_gen_prompts))
        registry.register(ConceptMapperAgent(prompts=_concept_mapper_prompts))

        graph = OrchestrationGraph.default()

        # Wire Neo4jRetrievalAdapter when graph features are enabled and Neo4j
        # is reachable; fall back to _StubRetrieval on connectivity failure so
        # the worker degrades gracefully without crashing.
        neo4j_ctx: Neo4jContext | None = None
        if settings.enable_graph:
            try:
                neo4j_ctx = Neo4jContext(
                    uri=settings.neo4j_uri,
                    username=settings.neo4j_username,
                    password=settings.neo4j_password,
                    database=settings.neo4j_database,
                )
                await neo4j_ctx.verify_connectivity()
                await neo4j_ctx.ensure_schema()
                retrieval: Any = Neo4jRetrievalAdapter(
                    neo4j_ctx,
                    gateway=gateway,
                    embedding_model="embedding",
                )
                logger.info("Neo4j graph layer active")
            except Exception:
                logger.warning(
                    "Neo4j unavailable; graph features disabled. "
                    "RelevanceGuard will accept all documents (empty-KB path).",
                    exc_info=True,
                )
                if neo4j_ctx is not None:
                    await neo4j_ctx.close()
                    neo4j_ctx = None
                retrieval = _StubRetrieval()
        else:
            retrieval = _StubRetrieval()

        # Outbox relay — forwards events inserted by this process to Redis Pub/Sub
        # for any ephemeral subscribers.  Runs in degraded (log-only) mode when
        # Redis is unavailable; relay is always started so outbox rows do not
        # accumulate unboundedly.
        redis_client: Any = None
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis

                redis_client = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
                await redis_client.ping()
                logger.info("Pipeline worker: Redis connected")
            except Exception:
                logger.warning(
                    "Pipeline worker: Redis unavailable, relay running in degraded mode",
                    exc_info=True,
                )
                redis_client = None

        relay: OutboxRelay | None = None
        try:
            relay = OutboxRelay(engine=engine, redis_client=redis_client)
            await relay.start()
            logger.info("Pipeline worker: OutboxRelay started")
        except Exception:
            logger.warning(
                "Pipeline worker: OutboxRelay failed to start", exc_info=True
            )
            relay = None

        # Periodic outbox retention: delete published events older than 7 days.
        async def _purge_loop() -> None:
            while True:
                await asyncio.sleep(3600)  # run every hour
                try:
                    deleted = await purge_published_events(engine)
                    if deleted:
                        logger.info("Purged %d old published outbox events", deleted)
                except Exception:
                    logger.warning("purge_published_events failed", exc_info=True)

        purge_task = asyncio.create_task(_purge_loop(), name="outbox-purge")

        # PipelineWorker builds a fresh per-task orchestrator (with its own
        # session) on each _execute_task call, so no long-lived shared session
        # is required here.
        worker = PipelineWorker(
            worker_id=_make_worker_id(),
            engine=engine,
            registry=registry,
            graph=graph,
            gateway=gateway,
            settings=processing_settings,
            retrieval=retrieval,
            max_concurrent=settings.max_concurrent_pipelines,
            stale_threshold_minutes=settings.pipeline_task_stale_threshold_minutes,
        )

        loop = asyncio.get_running_loop()

        def _on_signal() -> None:
            logger.info("Shutdown signal received")
            asyncio.create_task(worker.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _on_signal)
            except NotImplementedError:
                # Windows does not support add_signal_handler for all signals
                pass

        await worker.run_forever()

        purge_task.cancel()
        if relay is not None:
            await relay.stop()
        if redis_client is not None:
            await redis_client.aclose()
        if neo4j_ctx is not None:
            await neo4j_ctx.close()
        await engine.dispose()

    asyncio.run(_run())
