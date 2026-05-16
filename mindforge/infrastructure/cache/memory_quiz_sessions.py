"""In-memory quiz session store — used as last-resort fallback when neither
Redis nor PostgreSQL quiz session tables are available.

WARNING: Sessions are lost on process restart and are NOT shared across
workers. Use only in development or single-worker deployments.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from mindforge.domain.models import QuizSession


class InMemoryQuizSessionStore:
    """Thread-safe (asyncio-compatible) in-memory quiz session store."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, QuizSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session: QuizSession) -> None:
        async with self._lock:
            self._sessions[session.session_id] = session

    async def get_session(self, session_id: UUID) -> QuizSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            # Expire check
            if session.expires_at < datetime.now(timezone.utc):
                del self._sessions[session_id]
                return None
            return session

    async def update_session(self, session: QuizSession) -> None:
        async with self._lock:
            self._sessions[session.session_id] = session

    async def delete_session(self, session_id: UUID) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def close(self) -> None:
        pass
