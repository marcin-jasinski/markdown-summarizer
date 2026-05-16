"""Neo4j Retrieval Adapter — fulfils the ``RetrievalPort`` protocol.

Graph traversal is the primary retrieval strategy.  Full-text search is the
fallback when no concepts match.  Vector similarity is the last resort when
full-text returns nothing.

Priority (Section 10.3 / architecture cost guardrail):
    1. ``retrieve_concept_neighborhood()``  — graph traversal (cheapest)
    2. Full-text index on Chunk/Fact nodes
    3. Vector similarity on Chunk embeddings (most expensive, optional)
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from uuid import UUID

from mindforge.domain.models import (
    ConceptEdge,
    ConceptNeighborhood,
    ConceptNode,
    RelatedConceptSummary,
    RetrievalResult,
    TokenBudget,
    WeakConcept,
)
from mindforge.infrastructure.graph.cypher_queries import (
    FIND_WEAK_CONCEPTS,
    FULLTEXT_SEARCH,
    GET_CONCEPT_EDGES,
    GET_CONCEPTS,
    GET_LESSON_CONCEPTS,
    RETRIEVE_CONCEPT_NEIGHBORHOOD,
)
from mindforge.infrastructure.graph.neo4j_context import Neo4jContext
from mindforge.infrastructure.graph.normalizer import dedupe_key

log = logging.getLogger(__name__)

# Minimum ratio of concept label tokens that must appear in the query text
# for the concept to be considered "mentioned".
_MENTION_THRESHOLD = 1


class Neo4jRetrievalAdapter:
    """Fulfils the ``RetrievalPort`` protocol using Neo4j as the query store.

    Parameters
    ----------
    context:
        A live ``Neo4jContext``.
    gateway:
        ``AIGateway`` used for vector embedding when falling back to vector
        similarity.  May be ``None`` to disable vector search.
    embedding_model:
        Logical model name passed to ``gateway.embed()``.
    """

    def __init__(
        self,
        context: Neo4jContext,
        *,
        gateway: Any = None,
        embedding_model: str | None = None,
    ) -> None:
        self._ctx = context
        self._gateway = gateway
        self._embedding_model = embedding_model

    # ------------------------------------------------------------------
    # RetrievalPort protocol
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        kb_id: UUID,
        *,
        top_k: int = 5,
        budget: TokenBudget | None = None,
    ) -> list[RetrievalResult]:
        """Graph-first → full-text → vector retrieval.

        1. Scan all concepts in the KB, find those whose names appear in the
           query (simple keyword match is sufficient for now — NER is a Phase
           11 enhancement).
        2. For each matched concept, fetch its neighborhood.
        3. If no concepts matched, fall back to full-text search.
        4. If full-text returns nothing and a vector gateway is configured,
           fall back to vector similarity.
        """
        kb_id_str = str(kb_id)

        # Step 1 — concept extraction via simple keyword matching
        concepts = await self.get_concepts(kb_id)
        matched_keys = _extract_concept_keys(query, concepts)

        results: list[RetrievalResult] = []

        # Step 2 — graph neighborhood retrieval
        for key in matched_keys[:top_k]:
            neighborhood = await self.retrieve_concept_neighborhood(kb_id, key)
            if neighborhood is None:
                continue
            content = _neighborhood_to_text(neighborhood)
            results.append(
                RetrievalResult(
                    content=content,
                    source_lesson_id="",
                    source_document_id=UUID(int=0),
                    score=1.0,
                    metadata={"strategy": "graph", "concept_key": key},
                )
            )

        if results:
            return results[:top_k]

        # Step 3 — full-text fallback
        results = await self._fulltext_search(query, kb_id_str, top_k=top_k)
        if results:
            return results

        # Step 4 — vector similarity fallback (optional)
        if self._gateway and self._embedding_model:
            results = await self._vector_search(query, kb_id_str, top_k=top_k)

        return results[:top_k]

    async def retrieve_concept_neighborhood(
        self,
        kb_id: UUID,
        concept_key: str,
        *,
        depth: int = 2,
    ) -> ConceptNeighborhood | None:
        kb_id_str = str(kb_id)
        async with self._ctx.session() as session:
            result = await session.run(
                RETRIEVE_CONCEPT_NEIGHBORHOOD,
                concept_key=concept_key,
                kb_id=kb_id_str,
            )
            record = await result.single()

        if record is None:
            return None

        center = ConceptNode(
            key=record["concept_key"],
            label=record["concept_name"] or concept_key,
            description=record["concept_definition"] or "",
        )

        neighbors: list[RelatedConceptSummary] = []
        for n in record.get("neighbors") or []:
            if n.get("key") is None:
                continue
            neighbors.append(
                RelatedConceptSummary(
                    key=n["key"],
                    label=n.get("name") or n["key"],
                    relation=n.get("relation") or "RELATES_TO",
                    description=n.get("definition") or "",
                )
            )

        # Map fact texts collected by the Cypher query (previously discarded)
        facts = [f for f in (record.get("facts") or []) if f]

        return ConceptNeighborhood(
            center=center, neighbors=neighbors, depth=depth, facts=facts
        )

    async def find_weak_concepts(
        self,
        user_id: UUID,
        kb_id: UUID,
        today: date,
        *,
        limit: int = 10,
    ) -> list[WeakConcept]:
        kb_id_str = str(kb_id)
        user_id_str = str(user_id)
        async with self._ctx.session() as session:
            result = await session.run(
                FIND_WEAK_CONCEPTS,
                kb_id=kb_id_str,
                user_id=user_id_str,
                limit=limit,
            )
            records = await result.data()

        weak: list[WeakConcept] = []
        for r in records:
            last_review_raw = r.get("last_reviewed")
            last_review: date | None = None
            if last_review_raw and str(last_review_raw) != "1970-01-01":
                try:
                    last_review = date.fromisoformat(str(last_review_raw))
                except ValueError:
                    pass

            weak.append(
                WeakConcept(
                    key=r["key"],
                    label=r["name"] or r["key"],
                    due_count=int(r.get("graph_degree", 0)),
                    last_reviewed=last_review,
                )
            )
        return weak

    async def get_concepts(self, kb_id: UUID) -> list[ConceptNode]:
        kb_id_str = str(kb_id)
        async with self._ctx.session() as session:
            result = await session.run(GET_CONCEPTS, kb_id=kb_id_str)
            records = await result.data()

        return [
            ConceptNode(
                key=r["key"],
                label=r["name"] or r["key"],
                description=r.get("description") or "",
            )
            for r in records
        ]

    async def get_concept_edges(self, kb_id: UUID) -> list[ConceptEdge]:
        kb_id_str = str(kb_id)
        async with self._ctx.session() as session:
            result = await session.run(GET_CONCEPT_EDGES, kb_id=kb_id_str)
            records = await result.data()

        edges: list[ConceptEdge] = []
        seen: set[tuple[str, str]] = set()
        for r in records:
            src = r["source"]
            tgt = r["target"]
            if not src or not tgt or src == tgt:
                continue
            key = tuple(sorted((src, tgt)))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                ConceptEdge(
                    source=src,
                    target=tgt,
                    relation=r.get("relation") or "related_to",
                )
            )
        return edges

    async def get_lesson_concepts(
        self, kb_id: UUID, lesson_id: str
    ) -> list[ConceptNode]:
        kb_id_str = str(kb_id)
        async with self._ctx.session() as session:
            result = await session.run(
                GET_LESSON_CONCEPTS, kb_id=kb_id_str, lesson_id=lesson_id
            )
            records = await result.data()

        return [
            ConceptNode(
                key=r["key"],
                label=r["name"] or r["key"],
                description=r.get("description") or "",
            )
            for r in records
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fulltext_search(
        self, query: str, kb_id_str: str, top_k: int
    ) -> list[RetrievalResult]:
        try:
            async with self._ctx.session() as session:
                result = await session.run(
                    FULLTEXT_SEARCH,
                    query=query,
                    kb_id=kb_id_str,
                    top_k=top_k,
                )
                records = await result.data()
        except Exception:
            log.warning("Neo4j full-text search failed", exc_info=True)
            return []

        return [
            RetrievalResult(
                content=r["text"],
                source_lesson_id=r.get("lesson_id") or "",
                source_document_id=UUID(int=0),
                score=float(r.get("score", 0.0)),
                metadata={"strategy": "fulltext", "node_type": r.get("node_type")},
            )
            for r in records
        ]

    async def _vector_search(
        self, query: str, kb_id_str: str, top_k: int
    ) -> list[RetrievalResult]:
        try:
            vectors = await self._gateway.embed(
                model=self._embedding_model, texts=[query]
            )
            query_vector = vectors[0]
        except Exception:
            log.warning("Neo4j vector search: embedding failed", exc_info=True)
            return []

        try:
            # Over-fetch by 10x before the KB post-filter so the global top-k cut
            # does not starve a small KB when other KBs dominate the index.
            fetch_k = top_k * 10
            async with self._ctx.session() as session:
                result = await session.run(
                    """
                    CALL db.index.vector.queryNodes('chunk_embedding', $fetch_k, $vector)
                    YIELD node, score
                    WHERE node.kb_id = $kb_id
                    RETURN node.text AS text, node.lesson_id AS lesson_id, score
                    ORDER BY score DESC
                    LIMIT $top_k
                    """,
                    vector=query_vector,
                    kb_id=kb_id_str,
                    top_k=top_k,
                    fetch_k=fetch_k,
                )
                records = await result.data()
        except Exception:
            log.warning("Neo4j vector search query failed", exc_info=True)
            return []

        return [
            RetrievalResult(
                content=r["text"],
                source_lesson_id=r.get("lesson_id") or "",
                source_document_id=UUID(int=0),
                score=float(r.get("score", 0.0)),
                metadata={"strategy": "vector"},
            )
            for r in records
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_concept_keys(query: str, concepts: list[ConceptNode]) -> list[str]:
    """Return keys of concepts whose names are mentioned in *query*.

    Simple word-boundary matching on the normalised query text.  This is an
    intentionally lightweight heuristic; a proper NER pass is a Phase 11
    enhancement.
    """
    query_normalised = query.lower()
    matched: list[str] = []
    for concept in concepts:
        label_normalised = concept.label.lower()
        # Check if the concept label appears as a phrase in the query
        pattern = r"\b" + re.escape(label_normalised) + r"\b"
        if re.search(pattern, query_normalised):
            matched.append(concept.key)
    return matched


def _neighborhood_to_text(hood: ConceptNeighborhood) -> str:
    """Serialise a ``ConceptNeighborhood`` to a compact text context string."""
    lines: list[str] = [
        f"Concept: {hood.center.label}",
        f"Definition: {hood.center.description}",
    ]
    if hood.facts:
        lines.append("Key facts:")
        for f in hood.facts:
            lines.append(f"  - {f}")
    if hood.neighbors:
        lines.append("Related concepts:")
        for n in hood.neighbors:
            lines.append(f"  - {n.label} ({n.relation}): {n.description}")
    return "\n".join(lines)
