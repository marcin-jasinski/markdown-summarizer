"""Search router — hybrid Graph RAG + lexical + vector search."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mindforge.api.deps import get_current_user, get_kb_repo, get_search_service
from mindforge.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from mindforge.domain.models import User

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    kb_id: UUID,
    payload: SearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    search_service: Annotated[object, Depends(get_search_service)],
) -> SearchResponse:
    if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    result = await search_service.search(
        query=payload.query,
        kb_id=kb_id,
        user_id=current_user.user_id,
        top_k=payload.top_k,
    )
    return SearchResponse(
        query=result.query,
        results=[
            SearchResultItem(
                content=r.content,
                source_lesson_id=r.source_lesson_id,
                source_document_id=r.source_document_id,
                score=r.score,
                metadata=r.metadata,
            )
            for r in result.results
        ],
    )
