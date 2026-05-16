"""
Infrastructure — event system (Phase 8).

Public API surface:

* :class:`~mindforge.infrastructure.events.outbox_publisher.OutboxEventPublisher`
  — writes domain events to the outbox table inside the caller's transaction.
* :class:`~mindforge.infrastructure.events.outbox_relay.OutboxRelay`
  — polls the outbox and forwards events to Redis Pub/Sub.
* :func:`~mindforge.infrastructure.events.outbox_relay.purge_published_events`
  — housekeeping: delete events older than the retention window.
* :class:`~mindforge.infrastructure.events.durable_consumer.DurableEventConsumer`
  — base class for persistent, cursor-tracked event consumers.
* :class:`~mindforge.infrastructure.events.durable_consumer.GraphIndexerConsumer`
  — triggers Neo4j graph projection on ``ProcessingCompleted``.
* :class:`~mindforge.infrastructure.events.durable_consumer.AuditLoggerConsumer`
  — logs auditable events.
"""

from mindforge.infrastructure.events.durable_consumer import (
    AuditLoggerConsumer,
    DurableEventConsumer,
    GraphIndexerConsumer,
)
from mindforge.infrastructure.events.outbox_publisher import OutboxEventPublisher
from mindforge.infrastructure.events.outbox_relay import (
    OutboxRelay,
    purge_published_events,
)

__all__ = [
    "AuditLoggerConsumer",
    "DurableEventConsumer",
    "GraphIndexerConsumer",
    "OutboxEventPublisher",
    "OutboxRelay",
    "purge_published_events",
]
