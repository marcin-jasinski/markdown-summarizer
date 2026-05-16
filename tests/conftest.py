"""Shared pytest fixtures for all test suites."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from mindforge.domain.models import (
    CompletionResult,
    ConceptNeighborhood,
    ConceptEdge,
    ConceptNode,
    DeadlineProfile,
    RelatedConceptSummary,
    RetrievalResult,
    WeakConcept,
)


# ---------------------------------------------------------------------------
# StubAIGateway — typed test double for AIGateway protocol
# ---------------------------------------------------------------------------


class StubAIGateway:
    """Deterministic, in-memory AIGateway for use in tests.

    Usage::

        gateway = StubAIGateway()
        gateway.set_response("small", CompletionResult(...))
        result = await gateway.complete(model="small", messages=[...])

    Responses are keyed by **resolved** model name (after ``model_map``
    lookup).  Use ``"*"`` as a catch-all key.
    """

    def __init__(self, model_map: dict[str, str] | None = None) -> None:
        self._model_map: dict[str, str] = model_map or {}
        self._responses: dict[str, CompletionResult] = {}
        self._embed_responses: dict[str, list[list[float]]] = {}
        self.calls: list[dict[str, Any]] = []
        self.embed_calls: list[dict[str, Any]] = []

    def set_response(self, model_key: str, result: CompletionResult) -> None:
        """Register a canned response for a model key (logical or literal)."""
        self._responses[model_key] = result

    def set_embed_response(self, model_key: str, vectors: list[list[float]]) -> None:
        self._embed_responses[model_key] = vectors

    def _resolve(self, model: str) -> str:
        return self._model_map.get(model, model)

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        deadline: DeadlineProfile = DeadlineProfile.INTERACTIVE,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResult:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "deadline": deadline,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        resolved = self._resolve(model)
        if resolved in self._responses:
            return self._responses[resolved]
        if model in self._responses:
            return self._responses[model]
        if "*" in self._responses:
            return self._responses["*"]
        # Default: echo the last user message as content
        last_content = messages[-1].get("content", "") if messages else ""
        return CompletionResult(
            content=f"[stub] {last_content}",
            input_tokens=10,
            output_tokens=10,
            model=resolved,
            provider="stub",
            latency_ms=1.0,
            cost_usd=0.0,
        )

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
    ) -> list[list[float]]:
        self.embed_calls.append({"model": model, "texts": texts})
        resolved = self._resolve(model)
        if resolved in self._embed_responses:
            return self._embed_responses[resolved]
        if model in self._embed_responses:
            return self._embed_responses[model]
        if "*" in self._embed_responses:
            return self._embed_responses["*"]
        # Default: return zero vectors of dimension 4
        return [[0.0, 0.0, 0.0, 0.0] for _ in texts]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    """Return a real AppSettings loaded from environment / .env.

    Falls back to a minimal stub when pydantic-settings is not available
    (e.g., during bootstrapping before Phase 2 install completes).
    """
    try:
        from mindforge.infrastructure.config import AppSettings

        return AppSettings(
            enable_graph=False,
            enable_image_analysis=False,
            enable_tracing=False,
        )
    except Exception:
        stub = MagicMock(name="AppSettings")
        stub.enable_graph = False
        stub.enable_image_analysis = False
        stub.enable_tracing = False
        stub.max_document_size_mb = 10
        stub.chunk_max_tokens = 512
        stub.chunk_min_tokens = 64
        stub.chunk_overlap_tokens = 64
        return stub


@pytest.fixture
def mock_gateway() -> StubAIGateway:
    """Return a typed StubAIGateway that tracks calls and returns configurable results."""
    return StubAIGateway()


# ---------------------------------------------------------------------------
# StubRetrievalAdapter — typed test double for RetrievalPort protocol
# ---------------------------------------------------------------------------


class StubRetrievalAdapter:
    """In-memory RetrievalPort double for unit and integration tests.

    Pre-populate ``concepts``, ``neighborhoods``, and ``weak_concepts`` before
    the test to control retrieval results::

        stub = StubRetrievalAdapter()
        stub.concepts = [ConceptNode(key="ml", label="Machine Learning", description="...")]
        ctx = _make_context(retrieval=stub)
    """

    def __init__(self) -> None:
        self.concepts: list[ConceptNode] = []
        self.concept_edges: list[ConceptEdge] = []
        self.neighborhoods: dict[str, ConceptNeighborhood] = {}
        self.weak_concepts: list[WeakConcept] = []
        self.retrieval_results: list[RetrievalResult] = []
        self.calls: list[dict[str, Any]] = []

    async def retrieve(
        self,
        query: str,
        kb_id: UUID,
        *,
        top_k: int = 5,
        budget: Any = None,
    ) -> list[RetrievalResult]:
        self.calls.append({"method": "retrieve", "query": query, "kb_id": kb_id})
        return self.retrieval_results[:top_k]

    async def retrieve_concept_neighborhood(
        self,
        kb_id: UUID,
        concept_key: str,
        *,
        depth: int = 2,
    ) -> ConceptNeighborhood | None:
        self.calls.append(
            {
                "method": "retrieve_concept_neighborhood",
                "kb_id": kb_id,
                "concept_key": concept_key,
            }
        )
        return self.neighborhoods.get(concept_key)

    async def find_weak_concepts(
        self,
        user_id: UUID,
        kb_id: UUID,
        today: date,
        *,
        limit: int = 10,
    ) -> list[WeakConcept]:
        self.calls.append(
            {"method": "find_weak_concepts", "user_id": user_id, "kb_id": kb_id}
        )
        return self.weak_concepts[:limit]

    async def get_concepts(self, kb_id: UUID) -> list[ConceptNode]:
        self.calls.append({"method": "get_concepts", "kb_id": kb_id})
        return list(self.concepts)

    async def get_concept_edges(self, kb_id: UUID) -> list[ConceptEdge]:
        self.calls.append({"method": "get_concept_edges", "kb_id": kb_id})
        return list(self.concept_edges)

    async def get_lesson_concepts(
        self, kb_id: UUID, lesson_id: str
    ) -> list[ConceptNode]:
        self.calls.append(
            {
                "method": "get_lesson_concepts",
                "kb_id": kb_id,
                "lesson_id": lesson_id,
            }
        )
        return list(self.concepts)


@pytest.fixture
def stub_retrieval() -> StubRetrievalAdapter:
    """Return a typed StubRetrievalAdapter for use in agent and pipeline tests."""
    return StubRetrievalAdapter()
