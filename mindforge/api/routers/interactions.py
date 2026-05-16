"""Interaction history router — user's own interactions (redacted)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from mindforge.api.deps import get_current_user
from mindforge.api.schemas import InteractionResponse, InteractionTurnResponse
from mindforge.domain.models import User
from mindforge.infrastructure.persistence.interaction_repo import (
    PostgresInteractionStore,
)

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


@router.get("", response_model=list[InteractionResponse])
async def list_interactions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
) -> list[InteractionResponse]:
    async with request.app.state.session_factory() as session:
        store = PostgresInteractionStore(session)
        # list_for_user enforces redaction — no sensitive fields returned
        interactions = await store.list_for_user(
            current_user.user_id, limit=limit, offset=offset
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
