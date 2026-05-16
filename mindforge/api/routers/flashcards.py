"""Flashcards router — due cards, review submission, card listing."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mindforge.api.deps import (
    get_current_user,
    get_flashcard_service,
    get_kb_repo,
)
from mindforge.api.schemas import (
    DueCountResponse,
    FlashcardResponse,
    ReviewRequest,
)
from mindforge.application.flashcards import FlashcardService
from mindforge.domain.models import ReviewResult, User

router = APIRouter(
    prefix="/api/knowledge-bases/{kb_id}/flashcards", tags=["flashcards"]
)


@router.get("/due", response_model=list[FlashcardResponse])
async def get_due_cards(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    flashcard_service: Annotated[FlashcardService, Depends(get_flashcard_service)],
) -> list[FlashcardResponse]:
    if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    cards = await flashcard_service.get_due_cards(current_user.user_id, kb_id)
    return [
        FlashcardResponse(
            card_id=c.card_id,
            lesson_id=c.lesson_id,
            card_type=c.card_type.value,
            front=c.front,
            back=c.back,
            next_review=c.next_review.isoformat() if c.next_review else None,
            ease_factor=c.ease_factor,
            interval=c.interval,
        )
        for c in cards
    ]


@router.get("/due/count", response_model=DueCountResponse)
async def get_due_count(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    flashcard_service: Annotated[FlashcardService, Depends(get_flashcard_service)],
) -> DueCountResponse:
    count = await flashcard_service.due_count(current_user.user_id, kb_id)
    return DueCountResponse(due_count=count, kb_id=kb_id)


@router.post("/{card_id}/review", status_code=204)
async def review_card(
    kb_id: UUID,
    card_id: str,
    payload: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    flashcard_service: Annotated[FlashcardService, Depends(get_flashcard_service)],
) -> None:
    await flashcard_service.review_card(
        current_user.user_id,
        kb_id,
        card_id,
        ReviewResult(rating=payload.rating),
    )


@router.get("", response_model=list[FlashcardResponse])
async def list_cards(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    flashcard_service: Annotated[FlashcardService, Depends(get_flashcard_service)],
    lesson_id: str | None = None,
) -> list[FlashcardResponse]:
    """Return all flashcards in this KB (or filtered by lesson_id)."""
    if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    cards = await flashcard_service.list_all_cards(kb_id, lesson_id=lesson_id)
    return [
        FlashcardResponse(
            card_id=c.card_id,
            lesson_id=c.lesson_id,
            card_type=c.card_type.value,
            front=c.front,
            back=c.back,
        )
        for c in cards
    ]
