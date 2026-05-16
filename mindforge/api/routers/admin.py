"""Admin router — system metrics and unredacted interaction log.

Only accessible to users with is_admin=True.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from mindforge.api.deps import get_current_user
from mindforge.api.schemas import (
    InteractionResponse,
    InteractionTurnResponse,
    SystemMetricsResponse,
)
from mindforge.domain.models import User
from mindforge.infrastructure.persistence.interaction_repo import (
    PostgresInteractionStore,
)
from mindforge.infrastructure.persistence.models import (
    DocumentModel,
    InteractionModel,
    KnowledgeBaseModel,
    UserModel,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(current_user: User) -> User:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Brak uprawnień administratora.")
    return current_user


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SystemMetricsResponse:
    _require_admin(current_user)

    async with request.app.state.session_factory() as session:
        total_users = (
            await session.execute(select(func.count()).select_from(UserModel))
        ).scalar_one()
        total_kbs = (
            await session.execute(select(func.count()).select_from(KnowledgeBaseModel))
        ).scalar_one()
        total_docs = (
            await session.execute(select(func.count()).select_from(DocumentModel))
        ).scalar_one()
        total_interactions = (
            await session.execute(select(func.count()).select_from(InteractionModel))
        ).scalar_one()

    return SystemMetricsResponse(
        total_users=total_users,
        total_knowledge_bases=total_kbs,
        total_documents=total_docs,
        total_interactions=total_interactions,
    )


@router.get("/interactions", response_model=list[InteractionResponse])
async def list_all_interactions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[InteractionResponse]:
    """Return unredacted interaction log for admin tooling."""
    _require_admin(current_user)

    async with request.app.state.session_factory() as session:
        store = PostgresInteractionStore(session)
        interactions = await store.list_unredacted(
            user_id=user_id, limit=limit, offset=offset
        )

    return [
        InteractionResponse(
            interaction_id=i.interaction_id,
            interaction_type=i.interaction_type,
            created_at=i.created_at,
            knowledge_base_id=i.knowledge_base_id,
            completed_at=i.completed_at,
            turns=[
                InteractionTurnResponse(
                    turn_id=t.turn_id,
                    interaction_id=t.interaction_id,
                    turn_number=t.turn_number,
                    role=t.role,
                    content=t.content,
                    created_at=t.created_at,
                    tokens_used=t.tokens_used,
                )
                for t in i.turns
            ],
        )
        for i in interactions
    ]
