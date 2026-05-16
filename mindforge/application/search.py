"""
Application layer — Search Service.

Implements hybrid Graph RAG search with graph-first → full-text → vector
priority order (delegated to :class:`~mindforge.domain.ports.RetrievalPort`).
Records every search as an interaction turn for the audit trail.

No raw prompts, grounding context, or internal retrieval details are
returned to the caller.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

from mindforge.domain.models import RetrievalResult
from mindforge.domain.ports import AIGateway, InteractionStore, RetrievalPort

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result types (no raw prompts / grounding snippets)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResultItem:
    """Single search hit returned to the caller."""

    content: str
    source_lesson_id: str
    source_document_id: UUID
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """Aggregated search response — safe to expose to clients."""

    query: str
    results: list[SearchResultItem]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SearchService:
    """Hybrid Graph RAG search.

    Retrieval priority order: **graph → full-text → vector** (enforced inside
    the :class:`~mindforge.domain.ports.RetrievalPort` implementation; this
    service simply calls :meth:`retrieve` and trusts the adapter).

    Parameters
    ----------
    retrieval:
        Graph RAG retrieval port.
    gateway:
        AI gateway — reserved for optional LLM reranking (currently unused).
    interaction_store:
        Interaction store for audit trail recording.
    top_k:
        Default result count per query.
    """

    def __init__(
        self,
        retrieval: RetrievalPort,
        gateway: AIGateway,
        interaction_store: InteractionStore,
        *,
        top_k: int = 5,
    ) -> None:
        self._retrieval = retrieval
        self._gateway = gateway
        self._interactions = interaction_store
        self._default_top_k = top_k

    async def search(
        self,
        query: str,
        kb_id: UUID,
        user_id: UUID,
        *,
        top_k: int | None = None,
    ) -> SearchResult:
        """Perform hybrid search and record the interaction for audit.

        The :class:`~mindforge.domain.ports.RetrievalPort` implementation
        applies graph-first → full-text → vector priority internally.

        No raw prompts or grounding snippets are present in the return value.
        """
        k = top_k if top_k is not None else self._default_top_k
        t_start = time.monotonic()

        raw: list[RetrievalResult] = await self._retrieval.retrieve(
            query,
            kb_id,
            top_k=k,
        )

        duration_ms = round((time.monotonic() - t_start) * 1000)

        # Audit trail — do not let failures block the response
        try:
            interaction_id = await self._interactions.create_interaction(
                interaction_type="search",
                user_id=user_id,
                kb_id=kb_id,
            )
            await self._interactions.add_turn(
                interaction_id,
                actor_type="user",
                actor_id=str(user_id),
                action="search_query",
                input_data={"query": query, "top_k": k},
                output_data={"result_count": len(raw)},
                duration_ms=duration_ms,
            )
        except Exception:
            log.warning("Failed to record search interaction", exc_info=True)

        return SearchResult(
            query=query,
            results=[
                SearchResultItem(
                    content=r.content,
                    source_lesson_id=r.source_lesson_id,
                    source_document_id=r.source_document_id,
                    score=r.score,
                    metadata=r.metadata,
                )
                for r in raw
            ],
        )
