"""
Integration tests: document CRUD via PostgresDocumentRepository.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from mindforge.domain.models import (
    ContentHash,
    Document,
    DocumentStatus,
    LessonIdentity,
    UploadSource,
)
from mindforge.infrastructure.persistence.document_repo import (
    PostgresDocumentRepository,
)

pytestmark = pytest.mark.asyncio


def _make_document(**overrides) -> Document:
    defaults = dict(
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        lesson_identity=LessonIdentity(
            lesson_id="intro-python", title="Intro to Python"
        ),
        content_hash=ContentHash.compute(b"hello world"),
        source_filename="intro.md",
        mime_type="text/markdown",
        original_content="# Hello",
        upload_source=UploadSource.API,
        status=DocumentStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Document(**defaults)


# ---------------------------------------------------------------------------
# Helpers to create required prerequisite rows
# ---------------------------------------------------------------------------


async def _create_user(session) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import UserModel
    from datetime import datetime, timezone

    user = UserModel(display_name="Test User", created_at=datetime.now(timezone.utc))
    session.add(user)
    await session.flush()
    return user.user_id


async def _create_kb(session, owner_id: uuid.UUID) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import KnowledgeBaseModel

    kb = KnowledgeBaseModel(owner_id=owner_id, name="Test KB")
    session.add(kb)
    await session.flush()
    return kb.kb_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_save_and_get_by_id(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)

    doc = _make_document(knowledge_base_id=kb_id)
    repo = PostgresDocumentRepository(session)

    await repo.save(doc)
    fetched = await repo.get_by_id(doc.document_id)

    assert fetched is not None
    assert fetched.document_id == doc.document_id
    assert fetched.lesson_id == "intro-python"
    assert fetched.title == doc.title
    assert fetched.status == DocumentStatus.PENDING


@pytest.mark.integration
async def test_get_by_id_not_found(session):
    repo = PostgresDocumentRepository(session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.integration
async def test_dedup_check(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)

    content_hash = ContentHash.compute(b"unique content")
    doc = _make_document(knowledge_base_id=kb_id, content_hash=content_hash)
    repo = PostgresDocumentRepository(session)

    await repo.save(doc)

    # Same kb + same hash → found
    found = await repo.get_by_content_hash(kb_id, content_hash)
    assert found is not None
    assert found.document_id == doc.document_id

    # Different kb → not found (dedup is kb-scoped)
    owner2 = await _create_user(session)
    kb2_id = await _create_kb(session, owner2)
    not_found = await repo.get_by_content_hash(kb2_id, content_hash)
    assert not_found is None


@pytest.mark.integration
async def test_update_status(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)

    doc = _make_document(knowledge_base_id=kb_id)
    repo = PostgresDocumentRepository(session)
    await repo.save(doc)

    await repo.update_status(doc.document_id, DocumentStatus.DONE)
    updated = await repo.get_by_id(doc.document_id)
    assert updated is not None
    assert updated.status == DocumentStatus.DONE


@pytest.mark.integration
async def test_list_by_knowledge_base(session):
    owner_id = await _create_user(session)
    kb_id = await _create_kb(session, owner_id)

    repo = PostgresDocumentRepository(session)
    for i in range(3):
        doc = _make_document(
            knowledge_base_id=kb_id,
            lesson_identity=LessonIdentity(
                lesson_id=f"lesson-{i}", title=f"Lesson {i}"
            ),
            content_hash=ContentHash.compute(f"content {i}".encode()),
            source_filename=f"lesson_{i}.md",
        )
        await repo.save(doc)

    docs = await repo.list_by_knowledge_base(kb_id)
    assert len(docs) == 3
