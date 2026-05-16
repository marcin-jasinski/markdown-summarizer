"""Neo4j Graph Indexer — writes concept graph projections from pipeline artifacts.

Implements ``GraphIndexer`` protocol.  Call ``index_artifact()`` once a pipeline
run has completed; call ``remove_lesson()`` when a document is deleted or
superseded.  Call ``rebuild_knowledge_base()`` to fully regenerate a KB graph
from the current state of ``document_artifacts`` (back-fill / disaster recovery).

All writes are idempotent: every Cypher statement uses MERGE on deterministic
node IDs, so re-indexing the same artifact produces no duplicate nodes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from mindforge.domain.models import (
    ConceptMapData,
    DocumentArtifact,
    SummaryData,
)
from mindforge.infrastructure.graph.cypher_queries import (
    CREATE_ASSERTS_CONCEPT,
    CREATE_ASSERTS_RELATION,
    DELETE_LESSON_ENTITIES,
    DELETE_ORPHANED_CONCEPTS,
    MERGE_CHUNK,
    MERGE_CONCEPT,
    MERGE_FACT,
    MERGE_KNOWLEDGE_BASE,
    MERGE_LESSON,
    REBUILD_RELATES_TO_EDGES,
)
from mindforge.infrastructure.graph.neo4j_context import Neo4jContext
from mindforge.infrastructure.graph.normalizer import dedupe_key

log = logging.getLogger(__name__)

# Maximum number of nodes written in a single UNWIND batch
_BATCH_SIZE = 500


def _fact_id(lesson_id: str, text: str) -> str:
    return hashlib.sha256(f"{lesson_id}|{text}".encode()).hexdigest()[:16]


def _chunk_id(lesson_id: str, position: int, text: str) -> str:
    return hashlib.sha256(f"{lesson_id}|{position}|{text}".encode()).hexdigest()[:16]


def _relation_id(lesson_id: str, source_key: str, target_key: str, label: str) -> str:
    return hashlib.sha256(
        f"{lesson_id}|{source_key}|{target_key}|{label}".encode()
    ).hexdigest()[:16]


def _batched(items: list[Any], size: int = _BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


class Neo4jGraphIndexer:
    """Fulfils the ``GraphIndexer`` protocol.

    Parameters
    ----------
    context:
        A live ``Neo4jContext`` whose driver is already connected.
    embedding_model:
        Logical model name for the embedding gateway (e.g. ``"embedding"``).
        When ``None`` chunk embeddings are skipped.
    gateway:
        ``AIGateway`` instance; only used when ``embedding_model`` is set.
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
    # Public API — GraphIndexer protocol
    # ------------------------------------------------------------------

    async def index_artifact(
        self,
        artifact: DocumentArtifact,
        connection: Any = None,
    ) -> None:
        """Write or update the graph projection for the lesson described by
        *artifact*.

        The ``connection`` parameter is accepted for protocol compatibility but
        is not used — Neo4j has its own transaction management.
        """
        kb_id = str(artifact.knowledge_base_id)
        lesson_id = artifact.lesson_id

        log.info("Neo4jGraphIndexer: indexing lesson %s in KB %s", lesson_id, kb_id)

        async with self._ctx.session() as session:
            # 1. Delete old lesson entities
            await session.run(
                DELETE_LESSON_ENTITIES,
                lesson_id=lesson_id,
                kb_id=kb_id,
            )

            # 2. Remove orphaned concepts (no longer asserted by any lesson)
            await session.run(DELETE_ORPHANED_CONCEPTS, kb_id=kb_id)

            # 3. Ensure KnowledgeBase node exists
            await session.run(
                MERGE_KNOWLEDGE_BASE,
                kb_id=kb_id,
                name=kb_id,
            )

            # 4. Merge lesson node
            now_iso = datetime.now(timezone.utc).isoformat()
            await session.run(
                MERGE_LESSON,
                lesson_id=lesson_id,
                kb_id=kb_id,
                title=lesson_id,
                created_at=now_iso,
                updated_at=now_iso,
            )

            # 5. Write concepts from concept map
            if artifact.concept_map is not None:
                await self._write_concepts(session, artifact)

            # 6. Write facts from summary key_points
            if artifact.summary is not None:
                await self._write_facts(session, artifact)

            # 7. Write chunks from summary (use key_points as chunk proxies
            #    until real chunked content is wired through the artifact)
            if artifact.summary is not None:
                await self._write_chunks(session, artifact)

            # 8. Rebuild derived RELATES_TO projection for this KB
            await self._rebuild_relates_to(session, kb_id)

        log.info("Neo4jGraphIndexer: indexed lesson %s in KB %s", lesson_id, kb_id)

    async def remove_lesson(self, kb_id: UUID, lesson_id: str) -> None:
        """Remove all graph nodes and edges for a deactivated lesson."""
        kb_id_str = str(kb_id)
        log.info(
            "Neo4jGraphIndexer: removing lesson %s from KB %s", lesson_id, kb_id_str
        )
        async with self._ctx.session() as session:
            await session.run(
                DELETE_LESSON_ENTITIES,
                lesson_id=lesson_id,
                kb_id=kb_id_str,
            )
            await session.run(DELETE_ORPHANED_CONCEPTS, kb_id=kb_id_str)
            await self._rebuild_relates_to(session, kb_id_str)

    async def rebuild_knowledge_base(self, kb_id: UUID) -> None:
        """Full graph rebuild for *kb_id* (back-fill / disaster recovery).

        Delegates to external callers that iterate over all artifacts and call
        ``index_artifact()`` for each — this method simply clears the existing
        graph for the KB so the caller starts from a clean slate.
        """
        kb_id_str = str(kb_id)
        log.warning("Neo4jGraphIndexer: full rebuild requested for KB %s", kb_id_str)
        async with self._ctx.session() as session:
            # Delete the KnowledgeBase node and all its reachable entities
            await session.run(
                """
                MATCH (kb:KnowledgeBase {id: $kb_id})
                OPTIONAL MATCH (kb)<-[:BELONGS_TO]-(l:Lesson)
                OPTIONAL MATCH (l)-[:HAS_FACT]->(f:Fact)
                OPTIONAL MATCH (l)-[:HAS_CHUNK]->(ch:Chunk)
                OPTIONAL MATCH (l)-[:ASSERTS_RELATION]->(ra:RelationAssertion)
                DETACH DELETE f, ch, ra, l, kb
                """,
                kb_id=kb_id_str,
            )
            await session.run(
                """
                MATCH (c:Concept {kb_id: $kb_id})
                DETACH DELETE c
                """,
                kb_id=kb_id_str,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _write_concepts(
        self,
        session: Any,
        artifact: DocumentArtifact,
    ) -> None:
        concept_map = artifact.concept_map
        kb_id = str(artifact.knowledge_base_id)
        lesson_id = artifact.lesson_id

        concepts = [
            {
                "key": node.key,
                "name": node.label,
                "definition": node.description,
                "normalized_key": dedupe_key(node.label),
            }
            for node in concept_map.concepts
        ]

        for batch in _batched(concepts):
            await session.run(MERGE_CONCEPT, concepts=batch, kb_id=kb_id)

        # ASSERTS_CONCEPT assertions
        assertions = [
            {
                "key": node.key,
                "definition": node.description,
                "confidence": 1.0,
            }
            for node in concept_map.concepts
        ]
        for batch in _batched(assertions):
            await session.run(
                CREATE_ASSERTS_CONCEPT,
                assertions=batch,
                lesson_id=lesson_id,
                kb_id=kb_id,
            )

        # Relation assertions
        valid_keys = {n.key for n in concept_map.concepts}
        relations = [
            {
                "id": _relation_id(lesson_id, e.source, e.target, e.relation),
                "source_key": e.source,
                "target_key": e.target,
                "label": e.relation,
                "description": "",
            }
            for e in concept_map.edges
            if e.source in valid_keys and e.target in valid_keys
        ]
        for batch in _batched(relations):
            await session.run(
                CREATE_ASSERTS_RELATION,
                relations=batch,
                lesson_id=lesson_id,
                kb_id=kb_id,
            )

    async def _write_facts(
        self,
        session: Any,
        artifact: DocumentArtifact,
    ) -> None:
        summary = artifact.summary
        lesson_id = artifact.lesson_id
        kb_id = str(artifact.knowledge_base_id)

        key_points: list[str] = getattr(summary, "key_points", []) or []
        facts = [
            {
                "id": _fact_id(lesson_id, kp),
                "text": kp,
            }
            for kp in key_points
        ]
        for batch in _batched(facts):
            await session.run(MERGE_FACT, facts=batch, lesson_id=lesson_id, kb_id=kb_id)

    async def _write_chunks(
        self,
        session: Any,
        artifact: DocumentArtifact,
    ) -> None:
        """Write summary + key_points as Chunk nodes (Phase 7 placeholder).

        In Phase 8+ the pipeline artifact will carry real parsed chunks with
        position indices; until then the summary text and each key_point are
        used so the full-text index is populated and Graph RAG can fall back to
        it.
        """
        summary = artifact.summary
        lesson_id = artifact.lesson_id
        kb_id = str(artifact.knowledge_base_id)

        texts: list[str] = []
        if summary.summary:
            texts.append(summary.summary)
        texts.extend(getattr(summary, "key_points", []) or [])

        chunks = [
            {
                "id": _chunk_id(lesson_id, pos, text),
                "text": text,
                "position": pos,
            }
            for pos, text in enumerate(texts)
        ]

        for batch in _batched(chunks):
            await session.run(
                MERGE_CHUNK, chunks=batch, lesson_id=lesson_id, kb_id=kb_id
            )

        # Optionally embed chunks
        if self._gateway and self._embedding_model and chunks:
            await self._embed_chunks(session, chunks)

    async def _embed_chunks(
        self,
        session: Any,
        chunks: list[dict[str, Any]],
    ) -> None:
        from mindforge.infrastructure.graph.cypher_queries import SET_CHUNK_EMBEDDINGS

        texts = [c["text"] for c in chunks]
        try:
            vectors = await self._gateway.embed(
                model=self._embedding_model, texts=texts
            )
        except Exception:
            log.warning("Neo4jGraphIndexer: embedding failed, skipping", exc_info=True)
            return

        payload = [{"id": c["id"], "embedding": v} for c, v in zip(chunks, vectors)]
        for batch in _batched(payload):
            await session.run(SET_CHUNK_EMBEDDINGS, chunks=batch)

    @staticmethod
    async def _rebuild_relates_to(session: Any, kb_id: str) -> None:
        # REBUILD_RELATES_TO_EDGES contains two statements (DELETE then MERGE).
        # Both must run in a single explicit transaction so that a crash between
        # them never leaves the KB with zero RELATES_TO edges.
        from mindforge.infrastructure.graph.cypher_queries import (
            REBUILD_RELATES_TO_EDGES,
        )

        parts = [p.strip() for p in REBUILD_RELATES_TO_EDGES.split(";") if p.strip()]
        tx = await session.begin_transaction()
        try:
            for part in parts:
                await tx.run(part, kb_id=kb_id)
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
