"""
PostgreSQL implementation of `DocumentRepository`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import (
    ContentHash,
    Document,
    DocumentStatus,
    LessonIdentity,
    UploadSource,
)
from mindforge.infrastructure.persistence.models import DocumentModel


class PostgresDocumentRepository:
    """Fulfils the `DocumentRepository` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save(self, document: Document) -> None:
        """INSERT a new document row within the caller's session/transaction."""
        row = DocumentModel(
            document_id=document.document_id,
            kb_id=document.knowledge_base_id,
            lesson_id=document.lesson_identity.lesson_id,
            title=document.lesson_identity.title,
            revision=document.revision,
            is_active=document.is_active,
            content_sha256=document.content_hash.sha256,
            source_filename=document.source_filename,
            mime_type=document.mime_type,
            original_content=document.original_content,
            upload_source=document.upload_source.value.lower(),
            uploaded_by=document.uploaded_by,
            status=document.status.value.lower(),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        self._session.add(row)
        await self._session.flush()

    async def update_status(
        self, document_id: uuid.UUID, status: DocumentStatus
    ) -> None:
        await self._session.execute(
            update(DocumentModel)
            .where(DocumentModel.document_id == document_id)
            .values(status=status.value.lower(), updated_at=datetime.now(timezone.utc))
        )

    async def get_active_by_lesson(
        self, kb_id: uuid.UUID, lesson_id: str
    ) -> Document | None:
        """Return the currently active revision for a lesson in a KB, or None."""
        result = await self._session.execute(
            select(DocumentModel).where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.lesson_id == lesson_id,
                DocumentModel.is_active.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def deactivate_lesson(self, kb_id: uuid.UUID, lesson_id: str) -> int:
        """Atomically mark the active revision as inactive; return its revision number.

        Uses a single ``UPDATE … RETURNING`` statement to avoid a TOCTOU race
        between a SELECT and a subsequent ORM mutation when two concurrent
        ingestion requests target the same lesson in the same knowledge base.

        Returns 0 if no active document was found.
        """
        result = await self._session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.lesson_id == lesson_id,
                DocumentModel.is_active.is_(True),
            )
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
            .returning(DocumentModel.revision)
        )
        row = result.first()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.document_id == document_id)
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_by_content_hash(
        self, kb_id: uuid.UUID, content_hash: ContentHash
    ) -> Document | None:
        """Deduplication check scoped to a single knowledge base."""
        result = await self._session.execute(
            select(DocumentModel).where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.content_sha256 == content_hash.sha256,
            )
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_by_knowledge_base(
        self,
        kb_id: uuid.UUID,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        stmt = select(DocumentModel).where(DocumentModel.kb_id == kb_id)
        if active_only:
            stmt = stmt.where(DocumentModel.is_active.is_(True))
        stmt = (
            stmt.order_by(DocumentModel.created_at.desc()).limit(limit).offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# Mapping helper
# ---------------------------------------------------------------------------


def _to_domain(row: DocumentModel) -> Document:
    return Document(
        document_id=row.document_id,
        knowledge_base_id=row.kb_id,
        lesson_identity=LessonIdentity(lesson_id=row.lesson_id, title=row.title),
        content_hash=ContentHash(sha256=row.content_sha256),
        source_filename=row.source_filename,
        mime_type=row.mime_type,
        original_content=row.original_content,
        upload_source=UploadSource(row.upload_source.upper()),
        status=DocumentStatus(row.status.upper()),
        is_active=row.is_active,
        revision=row.revision,
        uploaded_by=row.uploaded_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
