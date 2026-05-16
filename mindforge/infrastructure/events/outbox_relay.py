"""
Outbox Relay — Phase 8 implementation.

Polls the ``outbox_events`` table and publishes undelivered events to
Redis Pub/Sub channels.  Uses ``FOR UPDATE SKIP LOCKED`` to prevent
double-publishing in concurrent deployments.

Guarantees
----------
* **At-least-once delivery** — an event is published to Redis before it is
  marked ``published=TRUE``.  If the process crashes between the two
  operations, the event will be re-published on the next relay cycle.
* **No lost events** — the relay never deletes events; deletion is handled
  separately by :func:`purge_published_events` (retention helper).

Wake-up strategy
----------------
1. **Fast path** — listen for ``pg_notify('outbox', '')`` via an
   ``asyncpg`` connection's ``LISTEN`` channel.  The publisher fires this
   after each commit.
2. **Slow path** — fall back to polling every ``poll_interval_seconds``
   (default 1 s) when the ``LISTEN`` channel is silent or when Redis is
   unavailable (degraded mode — events are simply logged but not forwarded
   to Redis).

Channel naming convention
-------------------------
Each event is published to ``events:{event_type}`` (e.g.
``events:ProcessingCompleted``).  Consumers subscribe to the channels they
care about.

Redis envelope format (JSON)::

    {
        "event_id":   "<uuid>",
        "event_type": "ProcessingCompleted",
        "payload":    { ... },
        "created_at": "2026-04-18T12:00:00.000000"
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

try:
    import asyncpg  # optional — used for pg_notify LISTEN
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

from mindforge.infrastructure.persistence.models import OutboxEventModel

log = logging.getLogger(__name__)

_BATCH_SIZE = 100
_DEFAULT_POLL_INTERVAL = 1.0  # seconds


class OutboxRelay:
    """Relay unpublished outbox events to Redis Pub/Sub.

    Parameters
    ----------
    engine:
        Async SQLAlchemy engine pointing at the canonical PostgreSQL store.
    redis_client:
        An ``aioredis`` / ``redis.asyncio`` client.  If ``None``, the relay
        runs in *log-only* degraded mode — events are not forwarded to Redis
        but are still marked as published so the outbox does not grow
        unboundedly.
    poll_interval_seconds:
        How long to sleep between polls when no ``pg_notify`` wakes the
        relay.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        redis_client: Any | None = None,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._engine = engine
        self._redis = redis_client
        self._poll_interval = poll_interval_seconds
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._notify_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the relay background task and pg_notify LISTEN task (if asyncpg available)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="outbox-relay")
        # Start the LISTEN task only when asyncpg is importable; otherwise the relay
        # falls back to polling every poll_interval_seconds.
        if asyncpg is not None:
            self._listen_task = asyncio.create_task(
                self._pg_listen_loop(), name="outbox-relay-listen"
            )
        log.info("OutboxRelay started (poll_interval=%.1fs)", self._poll_interval)

    async def stop(self) -> None:
        """Signal the relay to stop and wait for the current batch to finish."""
        self._running = False
        self._notify_event.set()  # wake up so the loop exits promptly
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listen_task = None
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                log.warning("OutboxRelay did not stop within 10 s; cancelling task")
                self._task.cancel()
            self._task = None
        log.info("OutboxRelay stopped")

    def notify(self) -> None:
        """Wake the relay immediately (called after each commit that queues an event)."""
        self._notify_event.set()

    # ------------------------------------------------------------------
    # PostgreSQL LISTEN loop (cross-process pg_notify wake-up)
    # ------------------------------------------------------------------

    async def _pg_listen_loop(self) -> None:
        """Open a raw asyncpg connection and LISTEN on the 'outbox' channel.

        Each notification sets ``_notify_event`` so the main relay loop wakes
        immediately instead of waiting for the next poll timeout.  This makes
        cross-process pg_notify signals (e.g., from the pipeline worker) work
        in addition to the in-process ``notify()`` call.
        """
        url = self._engine.url.render_as_string(hide_password=False).replace(
            "+asyncpg", ""
        )
        while self._running:
            conn: Any = None
            try:
                conn = await asyncpg.connect(url)

                def _on_notify(
                    connection: Any, pid: int, channel: str, payload: str
                ) -> None:  # noqa: ARG001
                    self._notify_event.set()

                await conn.add_listener("outbox", _on_notify)
                log.debug("OutboxRelay: LISTEN on pg channel 'outbox' established")
                # Keep the connection open; asyncpg calls _on_notify on each notification.
                while self._running:
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception:
                log.warning(
                    "OutboxRelay: pg LISTEN connection lost; reconnecting in 5 s",
                    exc_info=True,
                )
                await asyncio.sleep(5.0)
            finally:
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:  # pragma: no cover
                        pass

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            try:
                published = await self._flush_batch()
                if published < _BATCH_SIZE:
                    # Batch was smaller than the limit — nothing more to do right
                    # now; wait for a notify or the poll timeout.
                    try:
                        await asyncio.wait_for(
                            self._notify_event.wait(),
                            timeout=self._poll_interval,
                        )
                    except asyncio.TimeoutError:
                        pass
                    self._notify_event.clear()
            except Exception:
                log.exception("OutboxRelay: unexpected error in relay loop")
                await asyncio.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    async def _flush_batch(self) -> int:
        """Fetch up to ``_BATCH_SIZE`` unpublished events, publish, mark done.

        Returns the number of events processed.
        """
        async with self._session_factory() as session:
            async with session.begin():
                rows = await self._claim_batch(session)
                if not rows:
                    return 0

                for row in rows:
                    await self._publish_to_redis(row)

                event_ids = [row.event_id for row in rows]
                await session.execute(
                    update(OutboxEventModel)
                    .where(OutboxEventModel.event_id.in_(event_ids))
                    .values(
                        published=True,
                        published_at=datetime.now(tz=timezone.utc),
                    )
                )

                log.debug("OutboxRelay: published %d event(s)", len(rows))
                return len(rows)

    async def _claim_batch(self, session: AsyncSession) -> list[OutboxEventModel]:
        """SELECT … FOR UPDATE SKIP LOCKED to prevent double-publishing."""
        stmt = (
            select(OutboxEventModel)
            .where(OutboxEventModel.published.is_(False))
            .order_by(OutboxEventModel.sequence_num)
            .limit(_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _publish_to_redis(self, row: OutboxEventModel) -> None:
        """Publish a single event to Redis Pub/Sub.

        Runs in degraded mode (log-only) when ``self._redis`` is ``None``.
        """
        channel = f"events:{row.event_type}"
        envelope = json.dumps(
            {
                "event_id": str(row.event_id),
                "event_type": row.event_type,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            }
        )

        if self._redis is None:
            log.debug(
                "OutboxRelay (no Redis): event_type=%s event_id=%s",
                row.event_type,
                row.event_id,
            )
            return

        try:
            await self._redis.publish(channel, envelope)
            log.debug(
                "OutboxRelay: published event_type=%s to channel=%s",
                row.event_type,
                channel,
            )
        except Exception:
            log.exception("OutboxRelay: failed to publish to Redis channel=%s", channel)
            raise


# ---------------------------------------------------------------------------
# Retention helper
# ---------------------------------------------------------------------------


async def purge_published_events(
    engine: AsyncEngine,
    retention_days: int = 7,
) -> int:
    """Delete published outbox events older than ``retention_days`` days.

    Called from a periodic maintenance task (pipeline worker or cron).
    **Never** deletes unpublished events.

    Returns the number of rows deleted.
    """
    sql = text(
        "DELETE FROM outbox_events "
        "WHERE published = TRUE "
        "  AND published_at < now() - make_interval(days => :days)"
    ).bindparams(days=retention_days)

    async with engine.begin() as conn:
        result = await conn.execute(sql)
        deleted = result.rowcount
        log.info(
            "OutboxRelay: purged %d published event(s) older than %d days",
            deleted,
            retention_days,
        )
        return deleted
