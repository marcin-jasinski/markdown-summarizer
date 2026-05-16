"""
PostgreSQL implementation of `PipelineTaskStore`.

Inserts and queries `pipeline_tasks` rows within the caller's
active SQLAlchemy ``AsyncSession`` (shared transaction).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.infrastructure.persistence.models import (
    DocumentModel,
    PipelineTaskModel,
)


class PostgresPipelineTaskRepository:
    """Fulfils the ``PipelineTaskStore`` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_task(self, document_id: uuid.UUID) -> uuid.UUID:
        """INSERT a pending pipeline_task and return the generated ``task_id``."""
        task_id = uuid.uuid4()
        row = PipelineTaskModel(
            task_id=task_id,
            document_id=document_id,
            status="pending",
        )
        self._session.add(row)
        await self._session.flush()
        return task_id

    async def count_pending_for_user(self, user_id: uuid.UUID) -> int:
        """Return the count of pending/running tasks owned by ``user_id``."""
        result = await self._session.execute(
            select(func.count())
            .select_from(PipelineTaskModel)
            .join(
                DocumentModel,
                PipelineTaskModel.document_id == DocumentModel.document_id,
            )
            .where(
                DocumentModel.uploaded_by == user_id,
                PipelineTaskModel.status.in_(("pending", "running")),
            )
        )
        return result.scalar_one()
