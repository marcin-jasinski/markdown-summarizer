"""
Durable Event Consumers — Phase 8 implementation.

Provides the ``DurableEventConsumer`` abstract base class and two concrete
subclasses:

* :class:`GraphIndexerConsumer` — listens for ``ProcessingCompleted`` events
  and triggers Neo4j graph projection via the
  :class:`~mindforge.infrastructure.graph.neo4j_indexer.Neo4jGraphIndexer`.

* :class:`AuditLoggerConsumer` — records domain events as interaction-turn
  audit entries.

Design
------
Each consumer maintains a cursor in the ``consumer_cursors`` table keyed by
its :attr:`consumer_name`.  On each poll it fetches the next batch of
``outbox_events`` where ``sequence_num > cursor``, processes them, and
advances the cursor.  Processing is idempotent: re-delivering the same event
(identified by ``event_id``) has no additional effect.

Usage
-----
Consumers are long-running coroutines.  Start them with :meth:`start` (which
launches a background :class:`asyncio.Task`) and stop them cleanly with
:meth:`stop`.  Both methods are safe to call multiple times.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mindforge.infrastructure.persistence.models import (
    ConsumerCursorModel,
    InteractionModel,
    InteractionTurnModel,
    OutboxEventModel,
)

log = logging.getLogger(__name__)

_BATCH_SIZE = 100
_DEFAULT_POLL_INTERVAL = 2.0  # seconds
_MAX_RETRIES_PER_EVENT = 5  # after this many consecutive failures the event is skipped


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class DurableEventConsumer(ABC):
    """Poll-based durable event consumer backed by a PostgreSQL cursor.

    Subclasses implement :meth:`handle` to process individual events.

    Parameters
    ----------
    consumer_name:
        Unique identifier stored in ``consumer_cursors``.  Must be stable
        across restarts; changing it resets the cursor to 0 (replay all).
    engine:
        Async SQLAlchemy engine for the canonical store.
    poll_interval_seconds:
        Sleep duration between polls when the previous batch was empty.
    """

    def __init__(
        self,
        consumer_name: str,
        engine: AsyncEngine,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.consumer_name = consumer_name
        self._engine = engine
        self._poll_interval = poll_interval_seconds
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # In-memory retry counter: maps event_id -> consecutive failure count.
        # Resets to 0 on success; event is skipped (cursor advanced) once it
        # exceeds _MAX_RETRIES_PER_EVENT.
        self._retry_counts: dict[UUID, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch the consumer background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(
            self._loop(), name=f"consumer-{self.consumer_name}"
        )
        log.info("DurableEventConsumer '%s' started", self.consumer_name)

    async def stop(self) -> None:
        """Signal the consumer to stop and wait for the current batch to finish."""
        self._running = False
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=15.0)
            except asyncio.TimeoutError:
                log.warning(
                    "Consumer '%s' did not stop within 15 s; cancelling",
                    self.consumer_name,
                )
                self._task.cancel()
            self._task = None
        log.info("DurableEventConsumer '%s' stopped", self.consumer_name)

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    async def handle(
        self, event_type: str, payload: dict[str, Any], event_id: UUID
    ) -> None:
        """Process a single event.

        Parameters
        ----------
        event_type:
            The string name of the domain event class.
        payload:
            The deserialized event payload dict.
        event_id:
            The unique identifier from ``outbox_events.event_id``.  Implementations
            **must** use this for idempotency checks — the same event may be
            re-delivered after a crash/restart.
        """

    # ------------------------------------------------------------------
    # Internal polling loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            try:
                processed = await self._process_batch()
                if processed < _BATCH_SIZE:
                    await asyncio.sleep(self._poll_interval)
            except Exception:
                log.exception("Consumer '%s': unexpected error", self.consumer_name)
                await asyncio.sleep(self._poll_interval)

    async def _process_batch(self) -> int:
        """Fetch and process one batch of events; advance the cursor.

        Returns the number of events processed.
        """
        async with self._session_factory() as session:
            async with session.begin():
                cursor = await self._get_cursor(session)
                rows = await self._fetch_batch(session, cursor)
                if not rows:
                    return 0

                for row in rows:
                    try:
                        await self.handle(row.event_type, row.payload, row.event_id)
                        # Clear any previous failure count on success.
                        self._retry_counts.pop(row.event_id, None)
                    except Exception:
                        failures = self._retry_counts.get(row.event_id, 0) + 1
                        self._retry_counts[row.event_id] = failures
                        log.exception(
                            "Consumer '%s': error handling event_type=%s event_id=%s "
                            "(attempt %d/%d)",
                            self.consumer_name,
                            row.event_type,
                            row.event_id,
                            failures,
                            _MAX_RETRIES_PER_EVENT,
                        )
                        if failures < _MAX_RETRIES_PER_EVENT:
                            # Retry on the next poll cycle; do not advance cursor.
                            return 0
                        # Poison event: log at ERROR severity and skip past it so the
                        # consumer is not permanently stalled.  The event remains in
                        # outbox_events for manual inspection.
                        log.error(
                            "Consumer '%s': skipping poison event event_type=%s "
                            "event_id=%s after %d failures",
                            self.consumer_name,
                            row.event_type,
                            row.event_id,
                            failures,
                        )
                        self._retry_counts.pop(row.event_id, None)

                new_cursor = max(row.sequence_num for row in rows)
                await self._set_cursor(session, new_cursor)
                log.debug(
                    "Consumer '%s': processed %d event(s), cursor→%d",
                    self.consumer_name,
                    len(rows),
                    new_cursor,
                )
                return len(rows)

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    async def _get_cursor(self, session: AsyncSession) -> int:
        """Return the last processed sequence_num for this consumer (0 if new)."""
        stmt = select(ConsumerCursorModel).where(
            ConsumerCursorModel.consumer_name == self.consumer_name
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.last_sequence if row is not None else 0

    async def _set_cursor(self, session: AsyncSession, sequence: int) -> None:
        """Upsert the cursor for this consumer."""
        stmt = pg_insert(ConsumerCursorModel).values(
            consumer_name=self.consumer_name,
            last_sequence=sequence,
            updated_at=datetime.now(tz=timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["consumer_name"],
            set_={
                "last_sequence": stmt.excluded.last_sequence,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)

    async def _fetch_batch(
        self, session: AsyncSession, after_sequence: int
    ) -> list[OutboxEventModel]:
        """Fetch the next batch of events after ``after_sequence``."""
        stmt = (
            select(OutboxEventModel)
            .where(OutboxEventModel.sequence_num > after_sequence)
            .order_by(OutboxEventModel.sequence_num)
            .limit(_BATCH_SIZE)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Graph Indexer Consumer
# ---------------------------------------------------------------------------


class GraphIndexerConsumer(DurableEventConsumer):
    """On ``ProcessingCompleted`` events, load the artifact and call the graph indexer.

    Parameters
    ----------
    engine:
        Canonical PostgreSQL engine (used for cursor and artifact loading).
    graph_indexer:
        A live :class:`~mindforge.infrastructure.graph.neo4j_indexer.Neo4jGraphIndexer`
        instance.
    artifact_repo_factory:
        A callable that accepts an :class:`~sqlalchemy.ext.asyncio.AsyncSession`
        and returns an ``ArtifactRepository`` implementation.  Used to load the
        artifact for each ``ProcessingCompleted`` event.

    Idempotency: ``index_artifact`` uses Cypher MERGE operations, so re-delivering
    the same ``event_id`` produces no net change in Neo4j.
    """

    CONSUMER_NAME = "graph_indexer"

    def __init__(
        self,
        engine: AsyncEngine,
        graph_indexer: Any,
        artifact_repo_factory: Any,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        super().__init__(self.CONSUMER_NAME, engine, poll_interval_seconds)
        self._graph_indexer = graph_indexer
        self._artifact_repo_factory = artifact_repo_factory

    async def handle(
        self, event_type: str, payload: dict[str, Any], event_id: UUID
    ) -> None:  # noqa: ARG002
        """Index the lesson graph when a document finishes processing."""
        if event_type != "ProcessingCompleted":
            return

        document_id_str = payload.get("document_id")
        if not document_id_str:
            log.warning("GraphIndexerConsumer: missing document_id in payload")
            return

        document_id = UUID(document_id_str)

        async with self._session_factory() as session:
            repo = self._artifact_repo_factory(session)
            artifact = await repo.load_latest(document_id)

        if artifact is None:
            log.warning(
                "GraphIndexerConsumer: no artifact found for document_id=%s",
                document_id,
            )
            return

        log.info(
            "GraphIndexerConsumer: indexing document_id=%s lesson_id=%s",
            document_id,
            artifact.lesson_id,
        )
        await self._graph_indexer.index_artifact(artifact)
        log.info("GraphIndexerConsumer: indexed document_id=%s", document_id)


# ---------------------------------------------------------------------------
# Audit Logger Consumer
# ---------------------------------------------------------------------------


class AuditLoggerConsumer(DurableEventConsumer):
    """Record relevant domain events as ``interaction_turns`` rows for audit.

    Writes the following event types to ``interaction_turns`` (keyed by
    ``event_id`` in ``input_data`` for idempotency) and also logs them at
    INFO level:

    * ``DocumentIngested``
    * ``ProcessingCompleted``
    * ``ProcessingFailed``
    * ``QuizSessionStarted``
    * ``QuizAnswerEvaluated``
    * ``ReviewRecorded``

    Parameters
    ----------
    engine:
        Canonical PostgreSQL engine.
    interaction_repo_factory:
        A callable ``(AsyncSession) -> object`` that returns an object with
        ``create_interaction`` and ``add_turn`` coroutines compatible with
        :class:`~mindforge.infrastructure.persistence.interaction_repo.PostgresInteractionStore`.
        Used to persist the audit record.
    """

    CONSUMER_NAME = "audit_logger"

    _AUDITED_EVENTS = frozenset(
        {
            "DocumentIngested",
            "ProcessingCompleted",
            "ProcessingFailed",
            "QuizSessionStarted",
            "QuizAnswerEvaluated",
            "ReviewRecorded",
        }
    )

    def __init__(
        self,
        engine: AsyncEngine,
        interaction_repo_factory: Any,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        super().__init__(self.CONSUMER_NAME, engine, poll_interval_seconds)
        self._interaction_repo_factory = interaction_repo_factory

    async def handle(
        self, event_type: str, payload: dict[str, Any], event_id: UUID
    ) -> None:
        """Persist auditable events to interaction_turns and log them."""
        if event_type not in self._AUDITED_EVENTS:
            return

        log.info(
            "AUDIT event_type=%s %s",
            event_type,
            " ".join(f"{k}={v}" for k, v in payload.items() if k != "event_type"),
        )

        # Persist to interaction_turns so the audit trail survives process restarts.
        # Idempotency guard: check whether a turn carrying this event_id was already
        # written before inserting.  This prevents duplicate audit rows when the
        # durable-consumer batch is retried (e.g., after a handler failure mid-batch
        # causes the cursor not to advance).
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.execute(
                    select(InteractionTurnModel.turn_id)
                    .where(
                        InteractionTurnModel.input_data["event_id"].astext
                        == str(event_id)
                    )
                    .limit(1)
                )
                if existing.scalar_one_or_none() is not None:
                    log.debug(
                        "AuditLoggerConsumer: skipping already-recorded event_id=%s",
                        event_id,
                    )
                    return

                repo = self._interaction_repo_factory(session)
                interaction_id = await repo.create_interaction(
                    interaction_type=f"audit:{event_type}",
                )
                await repo.add_turn(
                    interaction_id,
                    actor_type="system",
                    actor_id=self.CONSUMER_NAME,
                    action=event_type,
                    input_data={"event_id": str(event_id), **payload},
                    output_data={},
                )
