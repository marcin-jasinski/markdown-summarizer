"""Pipeline task status router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mindforge.api.deps import get_current_user
from mindforge.api.schemas import TaskStatusResponse
from mindforge.domain.models import User
from mindforge.infrastructure.persistence.models import PipelineTaskModel

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskStatusResponse:
    async with request.app.state.session_factory() as session:
        result = await session.execute(
            select(PipelineTaskModel)
            .where(PipelineTaskModel.task_id == task_id)
            .options(selectinload(PipelineTaskModel.document))
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Zadanie nie istnieje.")

    if row.document is None or row.document.uploaded_by != current_user.user_id:
        raise HTTPException(status_code=404, detail="Zadanie nie istnieje.")

    return TaskStatusResponse(
        task_id=row.task_id,
        document_id=row.document_id,
        status=row.status,
        created_at=row.submitted_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        error_message=row.error,
        attempt_count=0,
    )
