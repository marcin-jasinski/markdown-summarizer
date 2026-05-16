"""Concepts router — return concept graph data for Cytoscape.js."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from mindforge.api.deps import get_current_user, get_kb_repo
from mindforge.api.schemas import (
    ConceptEdgeResponse,
    ConceptGraphResponse,
    ConceptNodeResponse,
)
from mindforge.domain.models import User

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/concepts", tags=["concepts"])


@router.get("", response_model=ConceptGraphResponse)
async def get_concepts(
    kb_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConceptGraphResponse:
    async with request.app.state.session_factory() as session:
        kb_repo = get_kb_repo(request, session)
        if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
            raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    retrieval = getattr(request.app.state, "retrieval", None)
    if retrieval is None:
        return ConceptGraphResponse(concepts=[], edges=[])

    nodes = await retrieval.get_concepts(kb_id)
    raw_edges = await retrieval.get_concept_edges(kb_id)

    valid_keys = {n.key for n in nodes}
    related_map: dict[str, set[str]] = {n.key: set() for n in nodes}

    edges: list[ConceptEdgeResponse] = []
    for e in raw_edges:
        if e.source not in valid_keys or e.target not in valid_keys:
            continue
        edges.append(
            ConceptEdgeResponse(
                source=e.source,
                target=e.target,
                relation=e.relation,
            )
        )
        related_map[e.source].add(e.target)
        related_map[e.target].add(e.source)

    concept_responses = [
        ConceptNodeResponse(
            key=n.key,
            label=n.label,
            description=n.description,
            related=sorted(related_map.get(n.key, set())),
        )
        for n in nodes
    ]

    return ConceptGraphResponse(concepts=concept_responses, edges=edges)
