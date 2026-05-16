"""
PostgreSQL implementation of `StudyProgressStore`.

SM-2 scheduling logic lives in ``mindforge.domain.models.sm2_update``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import (
    CardState,
    CardType,
    FlashcardData,
    ReviewResult,
    sm2_update,
)
from mindforge.infrastructure.persistence.models import StudyProgressModel


class PostgresStudyProgressRepository:
    """Fulfils the `StudyProgressStore` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_due_cards(
        self, user_id: uuid.UUID, kb_id: uuid.UUID, today: date
    ) -> list[CardState]:
        result = await self._session.execute(
            select(StudyProgressModel).where(
                StudyProgressModel.user_id == user_id,
                StudyProgressModel.kb_id == kb_id,
                StudyProgressModel.next_review <= today,
            )
        )
        return [_to_card_state(row) for row in result.scalars().all()]

    async def due_count(self, user_id: uuid.UUID, kb_id: uuid.UUID, today: date) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(StudyProgressModel)
            .where(
                StudyProgressModel.user_id == user_id,
                StudyProgressModel.kb_id == kb_id,
                StudyProgressModel.next_review <= today,
            )
        )
        return result.scalar_one() or 0

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_review(
        self,
        user_id: uuid.UUID,
        kb_id: uuid.UUID,
        card_id: str,
        review: ReviewResult,
    ) -> None:
        """UPSERT the card's SM-2 schedule based on the review rating."""
        # Load existing state or use defaults
        result = await self._session.execute(
            select(StudyProgressModel).where(
                StudyProgressModel.user_id == user_id,
                StudyProgressModel.kb_id == kb_id,
                StudyProgressModel.card_id == card_id,
            )
        )
        existing = result.scalar_one_or_none()

        ease_factor = existing.ease_factor if existing else 2.5
        interval = existing.interval if existing else 0
        repetitions = existing.repetitions if existing else 0

        ease_factor, interval, repetitions = sm2_update(
            rating=review.rating,
            ease_factor=ease_factor,
            interval=interval,
            repetitions=repetitions,
        )
        next_review = date.today() + timedelta(days=max(interval, 1))
        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(StudyProgressModel)
            .values(
                user_id=user_id,
                kb_id=kb_id,
                card_id=card_id,
                ease_factor=ease_factor,
                interval=interval,
                repetitions=repetitions,
                next_review=next_review,
                last_review=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "kb_id", "card_id"],
                set_={
                    "ease_factor": ease_factor,
                    "interval": interval,
                    "repetitions": repetitions,
                    "next_review": next_review,
                    "last_review": now,
                },
            )
        )
        await self._session.execute(stmt)


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _to_card_state(row: StudyProgressModel) -> CardState:
    return CardState(
        card_id=row.card_id,
        kb_id=row.kb_id,
        lesson_id="",  # lesson_id not stored in study_progress; resolved at service layer
        card_type=CardType.BASIC,
        front="",
        back="",
        next_review=row.next_review,
        interval=row.interval,
        ease_factor=row.ease_factor,
        repetitions=row.repetitions,
    )
