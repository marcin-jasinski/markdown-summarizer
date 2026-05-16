"""
Unit tests for Phase 11 — Search Service.

Covers:
  11.1.1  SearchService construction with required ports
  11.1.2  search() uses RetrievalPort with graph-first priority
  11.1.2  Record interaction turn (audit trail)
  11.1.2  SearchResult contains no raw prompts or grounding context
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from mindforge.application.search import SearchResult, SearchResultItem, SearchService
from mindforge.domain.models import RetrievalResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    retrieval=None,
    gateway=None,
    interaction_store=None,
    top_k: int = 5,
) -> SearchService:
    return SearchService(
        retrieval=retrieval or AsyncMock(),
        gateway=gateway or AsyncMock(),
        interaction_store=interaction_store or AsyncMock(),
        top_k=top_k,
    )


def _make_retrieval_result(
    content: str = "Some content",
    lesson_id: str = "python-basics",
    score: float = 0.9,
    document_id: UUID | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        content=content,
        source_lesson_id=lesson_id,
        source_document_id=document_id or uuid4(),
        score=score,
        metadata={},
    )


# ---------------------------------------------------------------------------
# SearchService construction
# ---------------------------------------------------------------------------


class TestSearchServiceConstruction:
    def test_instantiates_with_required_ports(self):
        service = _make_service()
        assert service is not None

    def test_default_top_k(self):
        service = _make_service(top_k=7)
        assert service._default_top_k == 7


# ---------------------------------------------------------------------------
# search() — retrieval delegation
# ---------------------------------------------------------------------------


class TestSearchDelegation:
    @pytest.mark.asyncio
    async def test_calls_retrieve_with_correct_args(self):
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = []
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )
        kb_id = uuid4()
        user_id = uuid4()

        await service.search("python variables", kb_id, user_id, top_k=3)

        retrieval.retrieve.assert_awaited_once_with("python variables", kb_id, top_k=3)

    @pytest.mark.asyncio
    async def test_uses_default_top_k_when_not_specified(self):
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = []
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store, top_k=10
        )
        kb_id = uuid4()

        await service.search("query", kb_id, uuid4())

        _, call_kwargs = retrieval.retrieve.call_args
        assert call_kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_maps_retrieval_results_to_search_result_items(self):
        doc_id = uuid4()
        raw = [_make_retrieval_result("content A", "lesson-1", 0.95, doc_id)]
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = raw
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )

        result = await service.search("q", uuid4(), uuid4())

        assert isinstance(result, SearchResult)
        assert result.query == "q"
        assert len(result.results) == 1
        item = result.results[0]
        assert item.content == "content A"
        assert item.source_lesson_id == "lesson-1"
        assert item.source_document_id == doc_id
        assert item.score == 0.95

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_no_hits(self):
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = []
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )
        result = await service.search("nothing", uuid4(), uuid4())

        assert result.results == []


# ---------------------------------------------------------------------------
# search() — audit trail
# ---------------------------------------------------------------------------


class TestSearchAuditTrail:
    @pytest.mark.asyncio
    async def test_records_interaction_on_search(self):
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = []
        interaction_store = AsyncMock()
        interaction_id = uuid4()
        interaction_store.create_interaction.return_value = interaction_id

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )
        kb_id = uuid4()
        user_id = uuid4()

        await service.search("test query", kb_id, user_id)

        interaction_store.create_interaction.assert_awaited_once_with(
            interaction_type="search",
            user_id=user_id,
            kb_id=kb_id,
        )
        interaction_store.add_turn.assert_awaited_once()
        turn_kwargs = interaction_store.add_turn.call_args.kwargs
        assert turn_kwargs["actor_type"] == "user"
        assert turn_kwargs["input_data"]["query"] == "test query"

    @pytest.mark.asyncio
    async def test_interaction_failure_does_not_block_response(self):
        """Audit trail failures must not propagate to the caller."""
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = [_make_retrieval_result()]
        interaction_store = AsyncMock()
        interaction_store.create_interaction.side_effect = RuntimeError("DB down")

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )
        result = await service.search("q", uuid4(), uuid4())

        # Search still works despite audit failure
        assert len(result.results) == 1


# ---------------------------------------------------------------------------
# Security invariant: no raw prompts / grounding context in results
# ---------------------------------------------------------------------------


class TestSearchSecurityInvariant:
    @pytest.mark.asyncio
    async def test_result_contains_no_sensitive_fields(self):
        raw = [_make_retrieval_result("safe content")]
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = raw
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(
            retrieval=retrieval, interaction_store=interaction_store
        )
        result = await service.search("q", uuid4(), uuid4())

        # SearchResult and SearchResultItem must not have these attributes
        assert not hasattr(result, "raw_prompt")
        assert not hasattr(result, "grounding_context")
        assert not hasattr(result, "reference_answer")
        assert not hasattr(result, "raw_completion")

        item = result.results[0]
        assert not hasattr(item, "raw_prompt")
        assert not hasattr(item, "grounding_context")
        assert not hasattr(item, "reference_answer")
