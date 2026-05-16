"""
PostgreSQL implementation of `ArtifactRepository`.

Artifacts are checkpointed per pipeline step.  Each checkpoint is an UPSERT
on `(document_id, version)` — the version is always the latest, bumped by
the pipeline orchestrator when starting a full reprocess.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import (
    CardType,
    ConceptEdge,
    ConceptMapData,
    ConceptNode,
    DocumentArtifact,
    FetchedArticle,
    FlashcardData,
    ImageDescription,
    StepCheckpoint,
    SummaryData,
    ValidationResult,
)
from mindforge.infrastructure.persistence.models import DocumentArtifactModel


class PostgresArtifactRepository:
    """Fulfils the `ArtifactRepository` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_checkpoint(self, artifact: DocumentArtifact) -> None:
        """UPSERT artifact JSON and step fingerprints within caller's transaction."""
        insert_stmt = pg_insert(DocumentArtifactModel).values(
            document_id=artifact.document_id,
            version=artifact.version,
            artifact_json=_artifact_to_dict(artifact),
            summary_json=_summary_to_dict(artifact.summary),
            flashcards_json=_flashcards_to_dict(artifact.flashcards),
            concept_map_json=_concept_map_to_dict(artifact.concept_map),
            validation_json=_validation_to_dict(artifact.validation_result),
            fingerprints_json=_fingerprints_to_dict(artifact.step_fingerprints),
            completed_step=artifact.completed_step,
            created_at=artifact.created_at,
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["document_id", "version"],
            set_={
                "artifact_json": insert_stmt.excluded.artifact_json,
                "summary_json": insert_stmt.excluded.summary_json,
                "flashcards_json": insert_stmt.excluded.flashcards_json,
                "concept_map_json": insert_stmt.excluded.concept_map_json,
                "validation_json": insert_stmt.excluded.validation_json,
                "fingerprints_json": insert_stmt.excluded.fingerprints_json,
                "completed_step": insert_stmt.excluded.completed_step,
            },
        )
        await self._session.execute(stmt)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def load_latest(self, document_id: uuid.UUID) -> DocumentArtifact | None:
        """Load the highest-version artifact for a document."""
        result = await self._session.execute(
            select(DocumentArtifactModel)
            .where(DocumentArtifactModel.document_id == document_id)
            .order_by(DocumentArtifactModel.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def count_flashcards(self, kb_id: uuid.UUID, lesson_id: str) -> int:
        """Count flashcards across all versions for a lesson."""
        from mindforge.infrastructure.persistence.models import DocumentModel

        # Join through documents to filter by kb_id and lesson_id
        result = await self._session.execute(
            select(DocumentArtifactModel)
            .join(
                DocumentModel,
                DocumentArtifactModel.document_id == DocumentModel.document_id,
            )
            .where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.lesson_id == lesson_id,
                DocumentModel.is_active.is_(True),
            )
            .order_by(DocumentArtifactModel.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None or row.flashcards_json is None:
            return 0
        cards = row.flashcards_json if isinstance(row.flashcards_json, list) else []
        return len(cards)

    async def list_flashcards_for_kb(
        self,
        kb_id: uuid.UUID,
        lesson_id: str | None = None,
    ) -> list[FlashcardData]:
        """Return all flashcards from the latest active artifact per document in a KB.

        When *lesson_id* is provided, only the artifact for that lesson is loaded.
        Used by ``FlashcardService`` to join card content with study-progress state.
        """
        from mindforge.infrastructure.persistence.models import DocumentModel

        # Subquery: latest version per document_id
        from sqlalchemy import func as sa_func

        latest_version_sq = (
            select(
                DocumentArtifactModel.document_id,
                sa_func.max(DocumentArtifactModel.version).label("max_version"),
            )
            .group_by(DocumentArtifactModel.document_id)
            .subquery()
        )

        conditions = [
            DocumentModel.kb_id == kb_id,
            DocumentModel.is_active.is_(True),
        ]
        if lesson_id is not None:
            conditions.append(DocumentModel.lesson_id == lesson_id)

        result = await self._session.execute(
            select(DocumentArtifactModel)
            .join(
                DocumentModel,
                DocumentArtifactModel.document_id == DocumentModel.document_id,
            )
            .join(
                latest_version_sq,
                (DocumentArtifactModel.document_id == latest_version_sq.c.document_id)
                & (DocumentArtifactModel.version == latest_version_sq.c.max_version),
            )
            .where(*conditions)
        )
        rows = result.scalars().all()

        all_cards: list[FlashcardData] = []
        for row in rows:
            all_cards.extend(_parse_flashcards(row.flashcards_json or []))
        return all_cards


def _artifact_to_dict(artifact: DocumentArtifact) -> dict[str, Any]:
    return {
        "document_id": str(artifact.document_id),
        "knowledge_base_id": str(artifact.knowledge_base_id),
        "lesson_id": artifact.lesson_id,
        "version": artifact.version,
        "created_at": artifact.created_at.isoformat(),
        "completed_step": artifact.completed_step,
    }


def _summary_to_dict(summary: SummaryData | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "summary": summary.summary,
        "key_points": summary.key_points,
        "topics": summary.topics,
    }


def _flashcards_to_dict(cards: list[FlashcardData]) -> list[dict[str, Any]]:
    return [
        {
            "card_id": c.card_id,
            "kb_id": str(c.kb_id),
            "lesson_id": c.lesson_id,
            "card_type": c.card_type.value,
            "front": c.front,
            "back": c.back,
            "tags": c.tags,
        }
        for c in cards
    ]


def _concept_map_to_dict(cm: ConceptMapData | None) -> dict[str, Any] | None:
    if cm is None:
        return None
    return {
        "concepts": [
            {
                "key": c.key,
                "label": c.label,
                "description": c.description,
                "related": c.related,
            }
            for c in cm.concepts
        ],
        "edges": [
            {"source": e.source, "target": e.target, "relation": e.relation}
            for e in cm.edges
        ],
    }


def _validation_to_dict(vr: ValidationResult | None) -> dict[str, Any] | None:
    if vr is None:
        return None
    return {
        "is_relevant": vr.is_relevant,
        "confidence": vr.confidence,
        "reason": vr.reason,
    }


def _fingerprints_to_dict(fps: dict[str, StepCheckpoint]) -> dict[str, Any]:
    return {
        step: {
            "output_key": cp.output_key,
            "fingerprint": cp.fingerprint,
            "completed_at": cp.completed_at.isoformat(),
        }
        for step, cp in fps.items()
    }


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------


def _to_domain(row: DocumentArtifactModel) -> DocumentArtifact:
    base = row.artifact_json or {}
    fingerprints = _parse_fingerprints(row.fingerprints_json or {})

    return DocumentArtifact(
        document_id=uuid.UUID(base["document_id"]),
        knowledge_base_id=uuid.UUID(base["knowledge_base_id"]),
        lesson_id=base["lesson_id"],
        version=row.version,
        created_at=row.created_at,
        summary=_parse_summary(row.summary_json),
        flashcards=_parse_flashcards(row.flashcards_json or []),
        concept_map=_parse_concept_map(row.concept_map_json),
        validation_result=_parse_validation(row.validation_json),
        step_fingerprints=fingerprints,
        completed_step=row.completed_step,
    )


def _parse_summary(data: dict | None) -> SummaryData | None:
    if not data:
        return None
    return SummaryData(
        summary=data.get("summary", ""),
        key_points=data.get("key_points", []),
        topics=data.get("topics", []),
    )


def _parse_flashcards(data: list[dict]) -> list[FlashcardData]:
    cards = []
    for d in data or []:
        card = FlashcardData(
            kb_id=uuid.UUID(d["kb_id"]),
            lesson_id=d["lesson_id"],
            card_type=CardType(d["card_type"]),
            front=d["front"],
            back=d["back"],
            tags=d.get("tags", []),
        )
        cards.append(card)
    return cards


def _parse_concept_map(data: dict | None) -> ConceptMapData | None:
    if not data:
        return None
    concepts = [
        ConceptNode(
            key=c["key"],
            label=c["label"],
            description=c["description"],
            related=c.get("related", []),
        )
        for c in data.get("concepts", [])
    ]
    edges = [
        ConceptEdge(source=e["source"], target=e["target"], relation=e["relation"])
        for e in data.get("edges", [])
    ]
    return ConceptMapData(concepts=concepts, edges=edges)


def _parse_validation(data: dict | None) -> ValidationResult | None:
    if not data:
        return None
    return ValidationResult(
        is_relevant=data["is_relevant"],
        confidence=data["confidence"],
        reason=data["reason"],
    )


def _parse_fingerprints(data: dict) -> dict[str, StepCheckpoint]:
    result = {}
    for step, cp in data.items():
        result[step] = StepCheckpoint(
            output_key=cp["output_key"],
            fingerprint=cp["fingerprint"],
            completed_at=datetime.fromisoformat(cp["completed_at"]),
        )
    return result
