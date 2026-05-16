"""
Transactional outbox publisher — Phase 8 implementation.

Writes domain events to the ``outbox_events`` table within the caller's
in-flight transaction, guaranteeing at-least-once delivery through the
:class:`OutboxRelay`.

Architecture note:
    The ``connection`` parameter is intentionally typed as ``Any`` at the
    domain-port level so that ``mindforge/domain/ports.py`` stays free of
    SQLAlchemy imports.  Here, in the infrastructure layer, we accept either
    an :class:`~sqlalchemy.ext.asyncio.AsyncSession` or a raw
    :class:`~sqlalchemy.ext.asyncio.AsyncConnection`; both expose a
    compatible ``execute()`` coroutine.

Usage:
    The publisher must be used inside an open transaction.  After the
    caller commits, ``pg_notify('outbox', '')`` is issued so the relay
    wakes up immediately rather than waiting for the next poll interval.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from mindforge.domain.events import DomainEvent
from mindforge.infrastructure.persistence.models import OutboxEventModel

log = logging.getLogger(__name__)


class OutboxEventPublisher:
    """Fulfils the ``EventPublisher`` port protocol.

    Parameters
    ----------
    session:
        An :class:`~sqlalchemy.ext.asyncio.AsyncSession` bound to the
        current request / unit-of-work.  The caller controls the
        transaction lifetime.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # EventPublisher protocol
    # ------------------------------------------------------------------

    async def publish_in_tx(self, event: DomainEvent, connection: Any) -> None:
        """INSERT the event into ``outbox_events`` within the caller's transaction.

        Parameters
        ----------
        event:
            A frozen domain event that exposes ``to_dict()``.
        connection:
            When provided as an :class:`~sqlalchemy.ext.asyncio.AsyncSession`,
            this method asserts that it is the **same** session object that was
            injected at construction time.  This guard ensures the event INSERT
            and the domain state change share the same unit-of-work, preserving
            the transactional outbox atomicity guarantee.  Pass ``None`` to skip
            the check (e.g. in tests).
        """
        if connection is not None and isinstance(connection, AsyncSession):
            if connection is not self._session:
                raise RuntimeError(
                    "OutboxEventPublisher.publish_in_tx received a different "
                    "AsyncSession than the one injected at construction time.  "
                    "The event INSERT and the domain state change must share the "
                    "same session to guarantee transactional atomicity."
                )
        event_id = uuid.uuid4()
        payload = event.to_dict()
        event_type = type(event).__name__

        stmt = pg_insert(OutboxEventModel).values(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            published=False,
        )

        await self._session.execute(stmt)
        log.debug(
            "Queued outbox event",
            extra={"event_id": str(event_id), "event_type": event_type},
        )


def make_outbox_publisher(session: AsyncSession) -> OutboxEventPublisher:
    """Factory used in composition roots."""
    return OutboxEventPublisher(session)


async def notify_outbox(connection: AsyncConnection | AsyncSession) -> None:
    """Issue ``pg_notify('outbox', '')`` after the containing transaction commits.

    Call this from the application layer immediately after the commit so
    :class:`~mindforge.infrastructure.events.outbox_relay.OutboxRelay` wakes
    up without waiting for the next polling interval.

    Parameters
    ----------
    connection:
        An already-committed connection or session.  ``pg_notify`` operates
        outside a transaction.
    """
    await connection.execute(text("SELECT pg_notify('outbox', '')"))
