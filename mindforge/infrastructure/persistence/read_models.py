"""
Read-model projection repository.

`lesson_projections` is a materialized view maintained by the pipeline after
each artifact flush.  It removes N+1 queries from the lessons list endpoint.
This is infrastructure — never a source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.infrastructure.persistence.models import LessonProjectionModel


class PostgresReadModelRepository:
    """Maintains `lesson_projections` read-model table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_lesson_projection(
        self,
        kb_id: uuid.UUID,
        lesson_id: str,
        document_id: uuid.UUID,
        title: str,
        flashcard_count: int = 0,
        concept_count: int = 0,
        summary_excerpt: str | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        now = processed_at or datetime.now(timezone.utc)
        stmt = (
            pg_insert(LessonProjectionModel)
            .values(
                kb_id=kb_id,
                lesson_id=lesson_id,
                document_id=document_id,
                title=title,
                flashcard_count=flashcard_count,
                concept_count=concept_count,
                summary_excerpt=summary_excerpt,
                processed_at=now,
            )
            .on_conflict_do_update(
                index_elements=["kb_id", "lesson_id"],
                set_={
                    "document_id": document_id,
                    "title": title,
                    "flashcard_count": flashcard_count,
                    "concept_count": concept_count,
                    "summary_excerpt": summary_excerpt,
                    "processed_at": now,
                },
            )
        )
        await self._session.execute(stmt)

    async def list_lessons(self, kb_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(LessonProjectionModel)
            .where(LessonProjectionModel.kb_id == kb_id)
            .order_by(LessonProjectionModel.lesson_id)
        )
        return [_to_dict(row) for row in result.scalars().all()]


def _to_dict(row: LessonProjectionModel) -> dict[str, Any]:
    return {
        "kb_id": str(row.kb_id),
        "lesson_id": row.lesson_id,
        "document_id": str(row.document_id),
        "title": row.title,
        "flashcard_count": row.flashcard_count,
        "concept_count": row.concept_count,
        "summary_excerpt": row.summary_excerpt,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }
