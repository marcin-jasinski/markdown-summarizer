"""PostgreSQL-backed quiz session store.

Used as the intermediate fallback when Redis is unavailable.  Sessions are
persisted to the ``quiz_sessions`` table (JSON column for questions, including
the server-side ``reference_answer`` — never exposed to the API layer).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)


class PostgresQuizSessionStore:
    """Store quiz sessions in PostgreSQL with ``quiz_sessions`` table."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ public

    async def create_session(self, session) -> None:
        from mindforge.infrastructure.persistence.models import QuizSessionModel

        row = QuizSessionModel(
            session_id=session.session_id,
            user_id=session.user_id,
            kb_id=session.kb_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            questions=[
                {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "reference_answer": q.reference_answer,
                    "grounding_context": q.grounding_context,
                    "lesson_id": q.lesson_id,
                }
                for q in session.questions
            ],
        )
        async with self._session_factory() as db:
            db.add(row)
            await db.commit()

    async def get_session(self, session_id: UUID):
        from mindforge.infrastructure.persistence.models import QuizSessionModel

        async with self._session_factory() as db:
            result = await db.execute(
                select(QuizSessionModel).where(
                    QuizSessionModel.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            await self.delete_session(session_id)
            return None

        return self._to_domain(row)

    async def update_session(self, session) -> None:
        """Replace the stored session row (upsert)."""
        from mindforge.infrastructure.persistence.models import QuizSessionModel

        row = QuizSessionModel(
            session_id=session.session_id,
            user_id=session.user_id,
            kb_id=session.kb_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            questions=[
                {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "reference_answer": q.reference_answer,
                    "grounding_context": q.grounding_context,
                    "lesson_id": q.lesson_id,
                }
                for q in session.questions
            ],
        )
        async with self._session_factory() as db:
            await db.merge(row)
            await db.commit()

    async def delete_session(self, session_id: UUID) -> None:
        from mindforge.infrastructure.persistence.models import QuizSessionModel

        async with self._session_factory() as db:
            await db.execute(
                delete(QuizSessionModel).where(
                    QuizSessionModel.session_id == session_id
                )
            )
            await db.commit()

    async def close(self) -> None:
        pass

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _to_domain(row):
        from mindforge.domain.models import QuizQuestion, QuizSession

        questions = [
            QuizQuestion(
                question_id=q["question_id"],
                question_text=q["question_text"],
                question_type=q["question_type"],
                reference_answer=q["reference_answer"],
                grounding_context=q["grounding_context"],
                lesson_id=q["lesson_id"],
            )
            for q in (row.questions or [])
        ]
        return QuizSession(
            session_id=row.session_id,
            user_id=row.user_id,
            kb_id=row.kb_id,
            questions=questions,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
