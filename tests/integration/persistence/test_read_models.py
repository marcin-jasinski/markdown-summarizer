"""
Integration tests: lesson projection upsert/list.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from mindforge.infrastructure.persistence.read_models import (
    PostgresReadModelRepository,
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

    kb = KnowledgeBaseModel(owner_id=owner_id, name="Proj KB")
    session.add(kb)
    await session.flush()
    return kb.kb_id


async def _create_document(session, kb_id) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import DocumentModel

    doc = DocumentModel(
        kb_id=kb_id,
        lesson_id="proj-lesson",
        content_sha256="d" * 64,
        source_filename="proj.md",
        mime_type="text/markdown",
        original_content="content",
        upload_source="api",
        status="done",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    await session.flush()
    return doc.document_id


@pytest.mark.integration
async def test_upsert_and_list(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)
    doc_id = await _create_document(session, kb_id)

    repo = PostgresReadModelRepository(session)
    await repo.upsert_lesson_projection(
        kb_id=kb_id,
        lesson_id="proj-lesson",
        document_id=doc_id,
        title="Projection Lesson",
        flashcard_count=5,
        concept_count=3,
        summary_excerpt="A short summary.",
    )

    lessons = await repo.list_lessons(kb_id)
    assert len(lessons) == 1
    assert lessons[0]["lesson_id"] == "proj-lesson"
    assert lessons[0]["title"] == "Projection Lesson"
    assert lessons[0]["flashcard_count"] == 5
    assert lessons[0]["concept_count"] == 3
    assert lessons[0]["summary_excerpt"] == "A short summary."


@pytest.mark.integration
async def test_upsert_is_idempotent(session):
    """Upserting the same lesson_id twice updates rather than inserting a duplicate."""
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)
    doc_id = await _create_document(session, kb_id)

    repo = PostgresReadModelRepository(session)
    await repo.upsert_lesson_projection(
        kb_id=kb_id,
        lesson_id="proj-lesson",
        document_id=doc_id,
        title="First Title",
        flashcard_count=1,
        concept_count=0,
    )
    await repo.upsert_lesson_projection(
        kb_id=kb_id,
        lesson_id="proj-lesson",
        document_id=doc_id,
        title="Updated Title",
        flashcard_count=10,
        concept_count=5,
    )

    lessons = await repo.list_lessons(kb_id)
    assert len(lessons) == 1
    assert lessons[0]["title"] == "Updated Title"
    assert lessons[0]["flashcard_count"] == 10


@pytest.mark.integration
async def test_list_empty_kb(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)

    repo = PostgresReadModelRepository(session)
    lessons = await repo.list_lessons(kb_id)
    assert lessons == []
