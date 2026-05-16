"""Knowledge base CRUD router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from mindforge.api.deps import (
    get_current_user,
    get_db_session,
    get_kb_repo,
    get_read_model_repo,
)
from mindforge.api.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    LessonResponse,
)
from mindforge.domain.models import User
from mindforge.infrastructure.persistence.kb_repo import PostgresKnowledgeBaseRepository
from mindforge.infrastructure.persistence.read_models import PostgresReadModelRepository

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


def _to_response(kb) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        kb_id=kb.kb_id,
        owner_id=kb.owner_id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at,
        document_count=kb.document_count,
        prompt_locale=kb.prompt_locale,
    )


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
) -> list[KnowledgeBaseResponse]:
    kbs = await kb_repo.list_by_owner(current_user.user_id)
    return [_to_response(kb) for kb in kbs]


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBaseResponse
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
) -> KnowledgeBaseResponse:
    try:
        kb = await kb_repo.create(
            owner_id=current_user.user_id,
            name=payload.name,
            description=payload.description,
            prompt_locale=payload.prompt_locale,
        )
        return _to_response(kb)
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Baza wiedzy o tej nazwie już istnieje.",
            )
        raise


@router.get("/{kb_id}/lessons", response_model=list[LessonResponse])
async def list_lessons(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
    read_model_repo: Annotated[
        PostgresReadModelRepository, Depends(get_read_model_repo)
    ],
) -> list[LessonResponse]:
    kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
    rows = await read_model_repo.list_lessons(kb_id)
    return [
        LessonResponse(
            lesson_id=row["lesson_id"],
            title=row["title"],
            document_count=1,
            flashcard_count=row["flashcard_count"],
            concept_count=row["concept_count"],
            last_processed_at=row["processed_at"],
        )
        for row in rows
    ]


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
) -> KnowledgeBaseResponse:
    kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
    return _to_response(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: UUID,
    payload: KnowledgeBaseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
) -> KnowledgeBaseResponse:
    kb = await kb_repo.update(
        kb_id,
        owner_id=current_user.user_id,
        name=payload.name,
        description=payload.description,
        prompt_locale=payload.prompt_locale,
    )
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
    return _to_response(kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
) -> None:
    deleted = await kb_repo.delete(kb_id, owner_id=current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
