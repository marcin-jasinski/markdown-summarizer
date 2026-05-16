"""Integration tests for the Neo4j graph layer (Phase 7).

Tests run against a real Neo4j instance (see conftest.py).  They verify:

- 7.7.1  Lesson indexing: concepts, facts, chunks created with correct IDs
- 7.7.2  Lesson revision cleanup: old entities deleted, orphaned concepts removed
- 7.7.3  Concept neighborhood retrieval
- 7.7.4  Weak concept detection query
- 7.7.5  MERGE idempotency: re-index same data → no duplicates
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio

from mindforge.domain.models import (
    ConceptEdge,
    ConceptMapData,
    ConceptNode,
    DocumentArtifact,
    SummaryData,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifact(
    lesson_id: str = "test-lesson",
    kb_id=None,
) -> DocumentArtifact:
    kb_id = kb_id or uuid4()
    artifact = DocumentArtifact(
        document_id=uuid4(),
        knowledge_base_id=kb_id,
        lesson_id=lesson_id,
        version=1,
        created_at=datetime.now(timezone.utc),
    )
    artifact.summary = SummaryData(
        summary="An introduction to machine learning concepts.",
        key_points=["Backpropagation computes gradients.", "SGD minimises the loss."],
        topics=["machine learning", "neural networks"],
    )
    artifact.concept_map = ConceptMapData(
        concepts=[
            ConceptNode(
                key="neural_network",
                label="Neural Network",
                description="A computing system inspired by biological neurons.",
            ),
            ConceptNode(
                key="backprop",
                label="Backpropagation",
                description="Algorithm to compute gradients for training.",
            ),
        ],
        edges=[
            ConceptEdge(
                source="backprop",
                target="neural_network",
                relation="USED_FOR",
            )
        ],
    )
    return artifact


def _fact_id(lesson_id: str, text: str) -> str:
    return hashlib.sha256(f"{lesson_id}|{text}".encode()).hexdigest()[:16]


def _chunk_id(lesson_id: str, position: int, text: str) -> str:
    return hashlib.sha256(f"{lesson_id}|{position}|{text}".encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 7.7.1 — Lesson indexing: correct nodes and IDs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLessonIndexing:
    async def test_concepts_are_created(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (c:Concept {kb_id: $kb_id}) RETURN c.key AS key ORDER BY c.key",
                kb_id=kb_id,
            )
            records = await result.data()

        keys = [r["key"] for r in records]
        assert "neural_network" in keys
        assert "backprop" in keys

    async def test_facts_have_deterministic_ids(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        lesson_id = artifact.lesson_id
        expected_id = _fact_id(lesson_id, "Backpropagation computes gradients.")

        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (f:Fact {id: $fid}) RETURN f.text AS text",
                fid=expected_id,
            )
            record = await result.single()

        assert record is not None
        assert "Backpropagation" in record["text"]

    async def test_chunks_are_created(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (ch:Chunk {kb_id: $kb_id}) RETURN count(ch) AS n",
                kb_id=kb_id,
            )
            record = await result.single()

        # At least the summary text + 2 key_points = 3 chunks
        assert record["n"] >= 3

    async def test_lesson_belongs_to_knowledge_base(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        kb_id = str(artifact.knowledge_base_id)
        lesson_id = artifact.lesson_id
        async with neo4j_ctx.session() as session:
            result = await session.run(
                """
                MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})-[:BELONGS_TO]->(kb:KnowledgeBase)
                RETURN kb.id AS kb_id
                """,
                lesson_id=lesson_id,
                kb_id=kb_id,
            )
            record = await result.single()

        assert record is not None
        assert record["kb_id"] == kb_id

    async def test_relates_to_edges_rebuilt(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            result = await session.run(
                """
                MATCH (:Concept {key: 'backprop', kb_id: $kb_id})
                      -[:RELATES_TO]->
                      (:Concept {key: 'neural_network', kb_id: $kb_id})
                RETURN count(*) AS n
                """,
                kb_id=kb_id,
            )
            record = await result.single()

        assert record["n"] == 1


# ---------------------------------------------------------------------------
# 7.7.2 — Lesson revision cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLessonRevisionCleanup:
    async def test_old_facts_deleted_on_reindex(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)

        # First index
        await indexer.index_artifact(artifact)

        lesson_id = artifact.lesson_id
        kb_id = str(artifact.knowledge_base_id)

        # Verify facts exist
        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (f:Fact {lesson_id: $lesson_id}) RETURN count(f) AS n",
                lesson_id=lesson_id,
            )
            before = (await result.single())["n"]
        assert before > 0

        # Re-index with different summary (fewer facts)
        artifact.summary = SummaryData(
            summary="Updated summary.",
            key_points=["Only one point now."],
            topics=["machine learning"],
        )
        await indexer.index_artifact(artifact)

        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (f:Fact {lesson_id: $lesson_id}) RETURN count(f) AS n",
                lesson_id=lesson_id,
            )
            after = (await result.single())["n"]

        # After reindex only the new facts remain (summary + 1 key_point = 2)
        assert after == 2
        assert after < before

    async def test_orphaned_concepts_removed_on_lesson_delete(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        # Remove the lesson
        await indexer.remove_lesson(artifact.knowledge_base_id, artifact.lesson_id)

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (c:Concept {kb_id: $kb_id}) RETURN count(c) AS n",
                kb_id=kb_id,
            )
            record = await result.single()

        # All concepts were only asserted by this one lesson — they should all
        # be gone after orphan cleanup
        assert record["n"] == 0

    async def test_shared_concept_survives_one_lesson_deletion(self, neo4j_ctx):
        """A concept shared between two lessons must survive when only one is deleted."""
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        kb_id = uuid4()

        artifact_a = _make_artifact(lesson_id="lesson-a", kb_id=kb_id)
        artifact_b = _make_artifact(lesson_id="lesson-b", kb_id=kb_id)
        # Both lessons assert "neural_network"

        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact_a)
        await indexer.index_artifact(artifact_b)

        # Delete lesson-a
        await indexer.remove_lesson(kb_id, "lesson-a")

        async with neo4j_ctx.session() as session:
            result = await session.run(
                "MATCH (c:Concept {key: 'neural_network', kb_id: $kb_id}) RETURN c",
                kb_id=str(kb_id),
            )
            record = await result.single()

        # Concept must still exist because lesson-b still asserts it
        assert record is not None


# ---------------------------------------------------------------------------
# 7.7.3 — Concept neighborhood retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConceptNeighborhoodRetrieval:
    async def test_neighborhood_center_returned(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        hood = await retrieval.retrieve_concept_neighborhood(
            artifact.knowledge_base_id, "neural_network"
        )

        assert hood is not None
        assert hood.center.key == "neural_network"
        assert "Neural Network" in hood.center.label

    async def test_neighborhood_includes_related_concepts(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        hood = await retrieval.retrieve_concept_neighborhood(
            artifact.knowledge_base_id, "neural_network"
        )

        assert hood is not None
        neighbor_keys = [n.key for n in hood.neighbors]
        # "backprop" is related to "neural_network" via RELATES_TO
        assert "backprop" in neighbor_keys

    async def test_unknown_concept_returns_none(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        hood = await retrieval.retrieve_concept_neighborhood(uuid4(), "no_such_concept")
        assert hood is None

    async def test_get_concepts_returns_all_in_kb(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        concepts = await retrieval.get_concepts(artifact.knowledge_base_id)

        keys = {c.key for c in concepts}
        assert "neural_network" in keys
        assert "backprop" in keys

    async def test_get_concept_edges_returns_relates_to(self, neo4j_ctx):
        """Regression: concept map needs RELATES_TO edges exposed via the port."""
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        edges = await retrieval.get_concept_edges(artifact.knowledge_base_id)

        # At least one edge between the two concepts in _make_artifact, deduplicated.
        assert edges, "expected at least one RELATES_TO edge"
        pair = {tuple(sorted((e.source, e.target))) for e in edges}
        assert ("backprop", "neural_network") in pair


# ---------------------------------------------------------------------------
# 7.7.4 — Weak concept detection (smoke test — no REVIEWED edges in test DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWeakConceptDetection:
    async def test_all_concepts_are_weak_when_never_reviewed(self, neo4j_ctx):
        from datetime import date

        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        weak = await retrieval.find_weak_concepts(
            user_id=uuid4(),
            kb_id=artifact.knowledge_base_id,
            today=date.today(),
            limit=10,
        )

        # Both concepts have never been reviewed → both appear in weak list
        assert len(weak) == 2
        weak_keys = {w.key for w in weak}
        assert "neural_network" in weak_keys
        assert "backprop" in weak_keys


# ---------------------------------------------------------------------------
# 7.7.5 — MERGE idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMergeIdempotency:
    async def test_reindex_same_artifact_no_duplicates(self, neo4j_ctx):
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)

        await indexer.index_artifact(artifact)
        await indexer.index_artifact(artifact)  # identical second run

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            # Check concepts
            result = await session.run(
                "MATCH (c:Concept {kb_id: $kb_id}) RETURN count(c) AS n",
                kb_id=kb_id,
            )
            concept_count = (await result.single())["n"]

            # Check RELATES_TO edges
            result = await session.run(
                """
                MATCH (:Concept {kb_id: $kb_id})-[r:RELATES_TO]->(:Concept {kb_id: $kb_id})
                RETURN count(r) AS n
                """,
                kb_id=kb_id,
            )
            edge_count = (await result.single())["n"]

        assert concept_count == 2  # exactly 2 concepts, no duplicates
        assert edge_count == 1  # exactly 1 RELATES_TO edge, no duplicates


# ---------------------------------------------------------------------------
# Regression — relation label fix (Finding 6 from phase review)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNeighborhoodRelationLabel:
    async def test_relation_label_is_not_asserts_concept(self, neo4j_ctx):
        """Regression: RETRIEVE_CONCEPT_NEIGHBORHOOD must return the semantic
        RELATES_TO edge label, not the internal 'ASSERTS_CONCEPT' type.

        Previously the query used ``type(nac)`` on the ASSERTS_CONCEPT relationship
        instead of ``rel.label`` on the RELATES_TO relationship, so every neighbor
        entry reported relation='ASSERTS_CONCEPT'.
        """
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        hood = await retrieval.retrieve_concept_neighborhood(
            artifact.knowledge_base_id, "neural_network"
        )

        assert hood is not None
        neighbor_keys = {n.key for n in hood.neighbors}
        assert "backprop" in neighbor_keys, "backprop must appear as a neighbor"

        backprop = next(n for n in hood.neighbors if n.key == "backprop")
        # Must NOT be the internal graph relationship type
        assert backprop.relation != "ASSERTS_CONCEPT", (
            "relation field must carry the semantic label (e.g. 'USED_FOR'), "
            "not the internal 'ASSERTS_CONCEPT' type"
        )
        # The test artifact defines the edge as USED_FOR
        assert backprop.relation == "USED_FOR"

    async def test_neighborhood_includes_facts(self, neo4j_ctx):
        """Regression: facts collected by the Cypher query were silently discarded
        because ConceptNeighborhood had no facts field (Finding 5 from phase review).
        """
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer
        from mindforge.infrastructure.graph.neo4j_retrieval import (
            Neo4jRetrievalAdapter,
        )

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)
        await indexer.index_artifact(artifact)

        retrieval = Neo4jRetrievalAdapter(neo4j_ctx)
        hood = await retrieval.retrieve_concept_neighborhood(
            artifact.knowledge_base_id, "neural_network"
        )

        assert hood is not None
        assert len(hood.facts) > 0, "ConceptNeighborhood.facts must be populated"
        facts_text = " ".join(hood.facts)
        # The test artifact contains "Backpropagation computes gradients." as a key point
        assert "Backpropagation" in facts_text or "SGD" in facts_text


# ---------------------------------------------------------------------------
# Regression — REBUILD_RELATES_TO atomicity (Finding 4 from phase review)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRebuildRelationshipAtomicity:
    async def test_relates_to_edges_present_after_reindex(self, neo4j_ctx):
        """Regression: ensure RELATES_TO edges survive a second index cycle.

        Previously the two DELETE+MERGE statements in REBUILD_RELATES_TO_EDGES
        ran as separate auto-commit transactions, so a failure between them
        could leave the KB with no RELATES_TO edges.  This test exercises the
        path by re-indexing twice and verifying the edge is always present.
        """
        from mindforge.infrastructure.graph.neo4j_indexer import Neo4jGraphIndexer

        artifact = _make_artifact()
        indexer = Neo4jGraphIndexer(neo4j_ctx)

        await indexer.index_artifact(artifact)
        # Second index run — exercises the DELETE+rebuild cycle again
        await indexer.index_artifact(artifact)

        kb_id = str(artifact.knowledge_base_id)
        async with neo4j_ctx.session() as session:
            result = await session.run(
                """
                MATCH (:Concept {key: 'backprop', kb_id: $kb_id})
                      -[:RELATES_TO]->
                      (:Concept {key: 'neural_network', kb_id: $kb_id})
                RETURN count(*) AS n
                """,
                kb_id=kb_id,
            )
            record = await result.single()

        assert (
            record["n"] == 1
        ), "RELATES_TO edge must exist after two consecutive index cycles"
