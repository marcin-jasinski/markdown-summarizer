"""Redis-backed quiz session store.

Sessions are stored as JSON-serialised ``QuizSession`` objects under the key
``quiz:session:<session_id>`` with a TTL equal to the session's lifetime.

Requires the ``redis.asyncio`` client (bundled in the ``redis`` package ≥ 4.x).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from mindforge.domain.models import QuizQuestion, QuizSession

log = logging.getLogger(__name__)

_SESSION_PREFIX = "quiz:session:"


class RedisQuizSessionStore:
    """Store quiz sessions in Redis with automatic TTL expiry."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _key(session_id: UUID) -> str:
        return f"{_SESSION_PREFIX}{session_id}"

    @staticmethod
    def _serialize(session) -> str:
        """Serialise a QuizSession domain object to JSON."""
        data = {
            "session_id": str(session.session_id),
            "user_id": str(session.user_id),
            "kb_id": str(session.kb_id),
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "questions": [
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
        }
        return json.dumps(data)

    @staticmethod
    def _deserialize(raw: str):
        """Deserialise JSON bytes back to a QuizSession domain object."""
        data = json.loads(raw)
        questions = [
            QuizQuestion(
                question_id=q["question_id"],
                question_text=q["question_text"],
                question_type=q["question_type"],
                reference_answer=q["reference_answer"],
                grounding_context=q["grounding_context"],
                lesson_id=q["lesson_id"],
            )
            for q in data.get("questions", [])
        ]
        return QuizSession(
            session_id=UUID(data["session_id"]),
            user_id=UUID(data["user_id"]),
            kb_id=UUID(data["kb_id"]),
            questions=questions,
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )

    # ------------------------------------------------------------------ public

    async def create_session(self, session) -> None:
        now = datetime.now(timezone.utc)
        ttl_seconds = max(1, int((session.expires_at - now).total_seconds()))
        await self._redis.setex(
            self._key(session.session_id),
            ttl_seconds,
            self._serialize(session),
        )

    async def get_session(self, session_id: UUID):
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        try:
            session = self._deserialize(raw if isinstance(raw, str) else raw.decode())
        except Exception:
            log.exception("Failed to deserialise quiz session %s", session_id)
            return None
        if session.expires_at < datetime.now(timezone.utc):
            await self.delete_session(session_id)
            return None
        return session

    async def update_session(self, session) -> None:
        """Replace the stored session (re-serialise with same TTL)."""
        now = datetime.now(timezone.utc)
        ttl_seconds = max(1, int((session.expires_at - now).total_seconds()))
        await self._redis.setex(
            self._key(session.session_id),
            ttl_seconds,
            self._serialize(session),
        )

    async def delete_session(self, session_id: UUID) -> None:
        await self._redis.delete(self._key(session_id))

    async def close(self) -> None:
        pass
