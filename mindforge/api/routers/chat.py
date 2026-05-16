"""Chat router — conversational RAG delegating to ChatService."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mindforge.api.deps import get_chat_service, get_current_user, get_kb_repo
from mindforge.api.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    StartChatRequest,
)
from mindforge.application.chat import (
    ChatSessionAccessDeniedError,
    ChatSessionNotFoundError,
)
from mindforge.domain.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def start_chat(
    payload: StartChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    chat_service: Annotated[object, Depends(get_chat_service)],
) -> ChatSessionResponse:
    if (
        await kb_repo.get_by_id(
            payload.knowledge_base_id, owner_id=current_user.user_id
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    info = await chat_service.start_session(
        current_user.user_id, payload.knowledge_base_id
    )
    return ChatSessionResponse(
        session_id=info.session_id,
        knowledge_base_id=info.knowledge_base_id,
        created_at=info.created_at,
        turns=[],
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: UUID,
    payload: ChatMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[object, Depends(get_chat_service)],
) -> ChatMessageResponse:
    """Process a chat message and return the AI answer.

    No grounding context, raw prompts, or raw completions are returned.
    """
    try:
        result = await chat_service.send_message(
            session_id, current_user.user_id, payload.message
        )
    except ChatSessionNotFoundError:
        raise HTTPException(status_code=404, detail="Sesja czatu nie istnieje.")
    except ChatSessionAccessDeniedError:
        raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji.")
    return ChatMessageResponse(
        session_id=result.session_id,
        answer=result.answer,
        source_concept_keys=result.source_concept_keys,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[object, Depends(get_chat_service)],
) -> list[ChatSessionResponse]:
    sessions = await chat_service.list_sessions(current_user.user_id, kb_id)
    return [
        ChatSessionResponse(
            session_id=s.session_id,
            knowledge_base_id=s.knowledge_base_id,
            created_at=s.created_at,
            turns=[],
        )
        for s in sessions
    ]
