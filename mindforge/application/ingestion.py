"""
Application layer — document ingestion service.

Handles document intake for all surfaces (API upload, Discord, Slack,
file watcher) in a single atomic transaction:

  1.  Sanitize filename.
  2.  Validate file size and format.
  3.  Compute content hash.
  4.  Reject duplicate (same content_hash in KB).
  5.  Enforce per-user pending task limit (429 guard).
  6.  Parse document → text and metadata.
  7.  Resolve lesson identity (lesson_id).
  8.  Deactivate previous active revision if one exists.
  9.  Persist new document (is_active=True, revision auto-incremented).
  10. Insert pipeline_task row (status=pending).
  11. Publish ``DocumentIngested`` outbox event.
  12. Return ``IngestionResult``.

The caller owns the database session (and must commit it).  All repository
and store objects are injected pre-constructed and share that session so that
all DB writes land in one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from mindforge.domain.events import DocumentIngested
from mindforge.domain.models import (
    ContentHash,
    Document,
    DocumentStatus,
    LessonIdentity,
    LessonIdentityError,
    UploadSource,
)
from mindforge.domain.ports import (
    DocumentParserRegistry,
    DocumentRepository,
    DocumentSanitizer,
    EventPublisher,
    PipelineTaskStore,
)


# ---------------------------------------------------------------------------
# Result and exception types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestionResult:
    document_id: UUID
    task_id: UUID
    lesson_id: str
    revision: int


class DuplicateContentError(ValueError):
    """Raised when the same content hash already exists in the knowledge base."""

    def __init__(self, kb_id: UUID, content_hash: str) -> None:
        self.kb_id = kb_id
        self.content_hash = content_hash
        super().__init__(
            f"Duplicate content: sha256={content_hash!r} already exists in KB {kb_id}"
        )


class PendingTaskLimitError(RuntimeError):
    """Raised when the user already has too many pending/running pipeline tasks."""

    def __init__(self, user_id: UUID, current_count: int, limit: int) -> None:
        self.user_id = user_id
        self.current_count = current_count
        self.limit = limit
        super().__init__(f"Masz {current_count} zadań w kolejce, poczekaj.")


class UploadRejectedError(ValueError):
    """Raised when a file is rejected at the security boundary (traversal, bad
    extension, oversized).  Distinct from content-identity failures so that
    adapters can return the correct HTTP status code (400/413/415 vs 422).
    """


class UnresolvableLessonError(ValueError):
    """Raised when no valid lesson_id can be derived from the uploaded document."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IngestionService:
    """Unified document intake service for all runtime surfaces."""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        sanitizer: DocumentSanitizer,
        parsers: DocumentParserRegistry,
        task_store: PipelineTaskStore,
        event_publisher: EventPublisher,
        *,
        max_pending_tasks_per_user: int = 10,
    ) -> None:
        self._doc_repo = doc_repo
        self._sanitizer = sanitizer
        self._parsers = parsers
        self._task_store = task_store
        self._event_publisher = event_publisher
        self._max_pending = max_pending_tasks_per_user

    async def ingest(
        self,
        raw_bytes: bytes,
        filename: str,
        knowledge_base_id: UUID,
        upload_source: UploadSource,
        uploaded_by: UUID | None = None,
        *,
        connection: object = None,
    ) -> IngestionResult:
        """Run the full ingestion transaction.

        The caller is responsible for committing the shared session after this
        method returns.  ``connection`` is forwarded verbatim to
        ``EventPublisher.publish_in_tx()`` — pass the active SQLAlchemy
        ``AsyncSession`` or ``AsyncConnection`` used by the repositories.
        """
        # Step 1 — sanitize filename (security boundary: path traversal, absolute paths)
        try:
            safe_name = self._sanitizer.sanitize_filename(filename)
        except ValueError as exc:
            raise UploadRejectedError(str(exc)) from exc

        # Step 2 — validate size and format (security boundary: unknown type, oversized)
        try:
            mime_type = self._sanitizer.validate(raw_bytes, safe_name)
        except ValueError as exc:
            raise UploadRejectedError(str(exc)) from exc

        # Step 3 — compute content hash
        content_hash = ContentHash.compute(raw_bytes)

        # Step 4 — deduplication check (scoped to KB)
        existing = await self._doc_repo.get_by_content_hash(
            knowledge_base_id, content_hash
        )
        if existing is not None:
            raise DuplicateContentError(knowledge_base_id, content_hash.sha256)

        # Step 5 — enforce per-user pending task limit
        if uploaded_by is not None:
            pending_count = await self._task_store.count_pending_for_user(uploaded_by)
            if pending_count >= self._max_pending:
                raise PendingTaskLimitError(
                    uploaded_by, pending_count, self._max_pending
                )

        # Step 6 — parse document to extract text and metadata
        parser = self._parsers.get(mime_type)
        parsed = parser.parse(raw_bytes, safe_name)

        # Step 7 — resolve lesson identity (rejects upload if no valid id)
        try:
            lesson_identity = LessonIdentity.resolve(parsed.metadata, safe_name)
        except LessonIdentityError as exc:
            raise UnresolvableLessonError(
                "Nie można ustalić identyfikatora lekcji. "
                "Dodaj pole 'lesson_id:' lub 'title:' do frontmatter dokumentu, "
                "albo zmień nazwę pliku."
            ) from exc

        # Step 8 — deactivate previous active revision if one exists
        prev_revision = await self._doc_repo.deactivate_lesson(
            knowledge_base_id, lesson_identity.lesson_id
        )
        new_revision = prev_revision + 1

        # Step 9 — build and persist the new document
        now = datetime.now(timezone.utc)
        document = Document(
            document_id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            lesson_identity=lesson_identity,
            content_hash=content_hash,
            source_filename=safe_name,
            mime_type=mime_type,
            original_content=parsed.text_content,
            content_blocks=parsed.content_blocks,
            upload_source=upload_source,
            uploaded_by=uploaded_by,
            status=DocumentStatus.PENDING,
            is_active=True,
            revision=new_revision,
            created_at=now,
            updated_at=now,
        )
        await self._doc_repo.save(document)

        # Step 10 — insert pipeline_task row
        task_id = await self._task_store.create_task(document.document_id)

        # Step 11 — publish DocumentIngested outbox event
        event = DocumentIngested(
            document_id=document.document_id,
            knowledge_base_id=knowledge_base_id,
            lesson_id=lesson_identity.lesson_id,
            upload_source=upload_source.value,
            content_sha256=content_hash.sha256,
            uploaded_by=uploaded_by,
            timestamp=now,
            revision=new_revision,
        )
        await self._event_publisher.publish_in_tx(event, connection)

        # Step 12 — return result (caller commits the session)
        return IngestionResult(
            document_id=document.document_id,
            task_id=task_id,
            lesson_id=lesson_identity.lesson_id,
            revision=new_revision,
        )
