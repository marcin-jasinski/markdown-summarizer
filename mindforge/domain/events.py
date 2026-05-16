"""
Domain layer — domain events.

All events are immutable value objects.  They are published after
state-changing operations and consumed by infrastructure adapters
(outbox publisher, graph indexer, notification handlers).

Pure Python only.  Zero I/O, zero framework imports.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a JSON-compatible dictionary."""
        result: dict[str, Any] = {
            "event_type": type(self).__name__,
        }
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if isinstance(value, UUID):
                result[f.name] = str(value)
            elif isinstance(value, datetime):
                result[f.name] = value.isoformat()
            else:
                result[f.name] = value
        return result


# ---------------------------------------------------------------------------
# Document lifecycle events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentIngested(DomainEvent):
    document_id: UUID
    knowledge_base_id: UUID
    lesson_id: str
    upload_source: str
    content_sha256: str
    uploaded_by: UUID | None
    timestamp: datetime
    revision: int = 1


@dataclass(frozen=True)
class PipelineStepCompleted(DomainEvent):
    document_id: UUID
    knowledge_base_id: UUID
    step_name: str
    fingerprint: str
    timestamp: datetime


@dataclass(frozen=True)
class ProcessingCompleted(DomainEvent):
    document_id: UUID
    knowledge_base_id: UUID
    lesson_id: str
    timestamp: datetime


@dataclass(frozen=True)
class ProcessingFailed(DomainEvent):
    document_id: UUID
    knowledge_base_id: UUID
    reason: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Graph projection events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphProjectionUpdated(DomainEvent):
    knowledge_base_id: UUID
    lesson_id: str
    concept_count: int
    edge_count: int
    timestamp: datetime


# ---------------------------------------------------------------------------
# Quiz events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuizSessionStarted(DomainEvent):
    session_id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    question_count: int
    timestamp: datetime


@dataclass(frozen=True)
class QuizAnswerEvaluated(DomainEvent):
    session_id: UUID
    user_id: UUID
    question_id: str
    rating: int
    timestamp: datetime


# ---------------------------------------------------------------------------
# Spaced-repetition events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewRecorded(DomainEvent):
    user_id: UUID
    knowledge_base_id: UUID
    card_id: str
    rating: int
    next_review_date: str  # ISO date string (no datetime import needed for date)
    timestamp: datetime
