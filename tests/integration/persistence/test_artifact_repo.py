"""
Integration tests: artifact checkpoint round-trip via PostgresArtifactRepository.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from mindforge.domain.models import (
    CardType,
    ConceptEdge,
    ConceptMapData,
    ConceptNode,
    DocumentArtifact,
    FlashcardData,
    StepCheckpoint,
    SummaryData,
    ValidationResult,
)
from mindforge.infrastructure.persistence.artifact_repo import (
    PostgresArtifactRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_user(session) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import UserModel

    u = UserModel(display_name="Test", created_at=datetime.now(timezone.utc))
    session.add(u)
    await session.flush()
    return u.user_id


async def _create_kb(session, owner_id) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import KnowledgeBaseModel

    kb = KnowledgeBaseModel(owner_id=owner_id, name="Test KB")
    session.add(kb)
    await session.flush()
    return kb.kb_id


async def _create_document(session, kb_id) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import DocumentModel

    doc = DocumentModel(
        kb_id=kb_id,
        lesson_id="test-lesson",
        content_sha256="a" * 64,
        source_filename="test.md",
        mime_type="text/markdown",
        original_content="content",
        upload_source="api",
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    await session.flush()
    return doc.document_id


def _make_artifact(document_id: uuid.UUID, kb_id: uuid.UUID) -> DocumentArtifact:
    card = FlashcardData(
        kb_id=kb_id,
        lesson_id="test-lesson",
        card_type=CardType.BASIC,
        front="What is Python?",
        back="A programming language",
    )
    artifact = DocumentArtifact(
        document_id=document_id,
        knowledge_base_id=kb_id,
        lesson_id="test-lesson",
        version=1,
        created_at=datetime.now(timezone.utc),
        summary=SummaryData(
            summary="A test summary", key_points=["point 1"], topics=["python"]
        ),
        flashcards=[card],
        concept_map=ConceptMapData(
            concepts=[
                ConceptNode(key="python", label="Python", description="A language")
            ],
            edges=[],
        ),
        validation_result=ValidationResult(
            is_relevant=True, confidence=0.9, reason="relevant"
        ),
        step_fingerprints={
            "summarizer": StepCheckpoint(
                output_key="summary",
                fingerprint="abc123",
                completed_at=datetime.now(timezone.utc),
            )
        },
        completed_step="summarizer",
    )
    return artifact


@pytest.mark.integration
async def test_save_and_load_artifact(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)
    doc_id = await _create_document(session, kb_id)

    artifact = _make_artifact(doc_id, kb_id)
    repo = PostgresArtifactRepository(session)

    await repo.save_checkpoint(artifact)
    loaded = await repo.load_latest(doc_id)

    assert loaded is not None
    assert loaded.document_id == doc_id
    assert loaded.version == 1
    assert loaded.summary is not None
    assert loaded.summary.summary == "A test summary"
    assert len(loaded.flashcards) == 1
    assert loaded.flashcards[0].front == "What is Python?"
    assert loaded.completed_step == "summarizer"
    assert "summarizer" in loaded.step_fingerprints
    assert loaded.step_fingerprints["summarizer"].fingerprint == "abc123"


@pytest.mark.integration
async def test_upsert_artifact(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)
    doc_id = await _create_document(session, kb_id)

    artifact = _make_artifact(doc_id, kb_id)
    repo = PostgresArtifactRepository(session)

    await repo.save_checkpoint(artifact)

    # Update the artifact
    artifact.summary = SummaryData(summary="Updated summary", key_points=[], topics=[])
    artifact.completed_step = "flashcard_generator"
    await repo.save_checkpoint(artifact)

    loaded = await repo.load_latest(doc_id)
    assert loaded is not None
    assert loaded.summary.summary == "Updated summary"
    assert loaded.completed_step == "flashcard_generator"


@pytest.mark.integration
async def test_load_latest_not_found(session):
    repo = PostgresArtifactRepository(session)
    result = await repo.load_latest(uuid.uuid4())
    assert result is None


@pytest.mark.integration
async def test_count_flashcards(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)
    doc_id = await _create_document(session, kb_id)

    artifact = _make_artifact(doc_id, kb_id)
    repo = PostgresArtifactRepository(session)
    await repo.save_checkpoint(artifact)

    count = await repo.count_flashcards(kb_id, "test-lesson")
    assert count == 1
