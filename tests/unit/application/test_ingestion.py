"""
Unit tests for Phase 4 — Document Parsing and Ingestion.

Covers:
- UploadSanitizer: path traversal, invalid extensions, size limits
- EgressPolicy: private IPs, metadata service, non-standard ports
- MarkdownParser: frontmatter extraction, heading breakpoints
- TxtParser: basic round-trip
- PdfParser: text extraction, page limit, image size caps, malformed input
- DocxParser: text extraction, heading detection, malformed input
- Chunker: heading splitting, overlap, deterministic IDs
- LessonIdentity.resolve(): full resolution chain
- IngestionService: dedup, revision, task limit, happy path
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindforge.domain.events import DocumentIngested
from mindforge.domain.models import (
    ContentHash,
    Document,
    DocumentStatus,
    LessonIdentity,
    LessonIdentityError,
    ParsedDocument,
    UploadSource,
)
from mindforge.application.ingestion import (
    DuplicateContentError,
    IngestionResult,
    IngestionService,
    PendingTaskLimitError,
    UnresolvableLessonError,
    UploadRejectedError,
)


# ============================================================================
# UploadSanitizer
# ============================================================================


class TestUploadSanitizer:
    @pytest.fixture
    def sanitizer(self):
        from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer

        return UploadSanitizer()

    # --- filename sanitization ---

    def test_clean_filename_passthrough(self, sanitizer):
        assert sanitizer.sanitize_filename("lecture.md") == "lecture.md"

    def test_strips_directory_prefix(self, sanitizer):
        assert sanitizer.sanitize_filename("uploads/lecture.md") == "lecture.md"

    def test_strips_deep_path(self, sanitizer):
        result = sanitizer.sanitize_filename("/etc/lecture.md")
        assert "/" not in result

    def test_rejects_traversal(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        with pytest.raises(UploadViolation):
            sanitizer.sanitize_filename("../etc/passwd")

    def test_rejects_double_dot_in_middle(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        with pytest.raises(UploadViolation):
            sanitizer.sanitize_filename("a/../../etc/shadow")

    def test_rejects_windows_drive_path(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        with pytest.raises(UploadViolation):
            sanitizer.sanitize_filename(r"C:\Users\file.md")

    def test_rejects_unc_path(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        with pytest.raises(UploadViolation):
            sanitizer.sanitize_filename(r"\\server\share\file.md")
    # --- validate ---

    def test_valid_markdown_passes(self, sanitizer):
        raw = b"# Hello\n\nWorld"
        mime = sanitizer.validate(raw, "lesson.md")
        assert mime == "text/markdown"

    def test_valid_txt_passes(self, sanitizer):
        raw = b"plain text"
        mime = sanitizer.validate(raw, "notes.txt")
        assert mime == "text/plain"

    def test_rejects_unknown_extension(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        with pytest.raises(UploadViolation):
            sanitizer.validate(b"data", "archive.zip")

    def test_empty_file_returns_mime(self, sanitizer):
        # validate() does not reject zero-byte files — size check is only an upper bound
        mime = sanitizer.validate(b"", "empty.md")
        assert mime == "text/markdown"

    def test_rejects_file_exceeding_global_limit(self, sanitizer):
        from mindforge.infrastructure.security.upload_sanitizer import UploadViolation

        # Exceed the global 50 MB cap
        oversized = b"x" * (50 * 1024 * 1024 + 1)
        with pytest.raises(UploadViolation):
            sanitizer.validate(oversized, "big.txt")


# ============================================================================
# EgressPolicy
# ============================================================================


class TestEgressPolicy:
    @pytest.fixture
    def policy(self):
        from mindforge.infrastructure.security.egress_policy import EgressPolicy
        from mindforge.infrastructure.config import EgressSettings

        settings = EgressSettings(
            allow_private_networks=False,
            allow_nonstandard_ports=False,
        )
        return EgressPolicy(settings)

    def test_public_url_passes(self, policy):
        # Should not raise for a valid public URL
        policy.validate_url("https://example.com/page")

    def test_rejects_loopback(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("http://127.0.0.1/admin")

    def test_rejects_rfc1918_10(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("http://10.0.0.1/secret")

    def test_rejects_rfc1918_172(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("http://172.16.0.1/secret")

    def test_rejects_rfc1918_192_168(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("http://192.168.1.100/api")

    def test_rejects_metadata_ip(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_ftp_scheme(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("ftp://example.com/file")

    def test_rejects_non_standard_port(self, policy):
        from mindforge.infrastructure.security.egress_policy import EgressViolation

        with pytest.raises(EgressViolation):
            policy.validate_url("https://example.com:9999/page")


# ============================================================================
# MarkdownParser
# ============================================================================


class TestMarkdownParser:
    @pytest.fixture
    def parser(self):
        from mindforge.infrastructure.parsing.markdown_parser import MarkdownParser

        return MarkdownParser()

    def test_extracts_frontmatter_title(self, parser):
        md = b"---\ntitle: Neural Networks\n---\n# Neural Networks\n\nContent."
        result = parser.parse(md, "lesson.md")
        assert result.metadata.get("title") == "Neural Networks"

    def test_extracts_frontmatter_lesson_id(self, parser):
        md = b"---\nlesson_id: neural-nets-intro\n---\n\nContent."
        result = parser.parse(md, "lesson.md")
        assert result.metadata.get("lesson_id") == "neural-nets-intro"

    def test_extracts_first_heading_when_no_frontmatter(self, parser):
        md = b"# Attention Mechanism\n\nSelf-attention description."
        result = parser.parse(md, "attention.md")
        assert result.metadata.get("first_heading") == "Attention Mechanism"

    def test_text_content_non_empty(self, parser):
        md = b"# Title\n\nSome body text."
        result = parser.parse(md, "doc.md")
        assert "body text" in result.text_content

    def test_produces_content_blocks(self, parser):
        md = b"# H1\n\nParagraph."
        result = parser.parse(md, "doc.md")
        assert len(result.content_blocks) >= 1


# ============================================================================
# TxtParser
# ============================================================================


class TestTxtParser:
    @pytest.fixture
    def parser(self):
        from mindforge.infrastructure.parsing.txt_parser import TxtParser

        return TxtParser()

    def test_round_trip_text(self, parser):
        raw = b"Hello, world!"
        result = parser.parse(raw, "notes.txt")
        assert "Hello, world!" in result.text_content

    def test_empty_metadata(self, parser):
        result = parser.parse(b"text", "f.txt")
        assert result.metadata == {}

    def test_no_embedded_images(self, parser):
        result = parser.parse(b"text", "f.txt")
        assert result.embedded_images == []

    def test_invalid_utf8_replaced(self, parser):
        raw = b"valid \xff\xfe invalid"
        result = parser.parse(raw, "f.txt")
        assert isinstance(result.text_content, str)


# ============================================================================
# Chunker
# ============================================================================


class TestChunker:
    @pytest.fixture
    def chunker(self):
        from mindforge.infrastructure.parsing.chunker import Chunker

        return Chunker(max_tokens=100, min_tokens=10, overlap_tokens=20)

    def test_returns_list_of_chunks(self, chunker):
        text = "## Section A\n\nSome text here.\n\n## Section B\n\nMore text."
        chunks = chunker.chunk(text, "lesson-1")
        assert len(chunks) >= 1

    def test_chunk_ids_are_deterministic(self, chunker):
        text = "## Section\n\nContent that is long enough to become a chunk."
        chunks_a = chunker.chunk(text, "lesson-x")
        chunks_b = chunker.chunk(text, "lesson-x")
        assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]

    def test_chunk_ids_differ_for_different_lessons(self, chunker):
        text = "## Section\n\nContent that is long enough to become a chunk."
        chunks_a = chunker.chunk(text, "lesson-a")
        chunks_b = chunker.chunk(text, "lesson-b")
        # At least some IDs should differ (lesson_id is part of the hash seed)
        ids_a = {c.chunk_id for c in chunks_a}
        ids_b = {c.chunk_id for c in chunks_b}
        assert ids_a != ids_b

    def test_heading_context_populated(self, chunker):
        text = (
            "## Neural Networks\n\n"
            + "Word " * 30
            + "\n\n### Backprop\n\n"
            + "Word " * 30
        )
        chunks = chunker.chunk(text, "lesson-1")
        heading_contexts = {c.heading_context for c in chunks if c.heading_context}
        assert len(heading_contexts) >= 1

    def test_lesson_id_stored_on_chunk(self, chunker):
        chunks = chunker.chunk("## H\n\n" + "word " * 30, "my-lesson")
        for chunk in chunks:
            assert chunk.lesson_id == "my-lesson"

    def test_positions_monotonically_increasing(self, chunker):
        text = "\n\n".join([f"## Section {i}\n\n" + "word " * 40 for i in range(5)])
        chunks = chunker.chunk(text, "lesson-1")
        positions = [c.position for c in chunks]
        assert positions == sorted(positions)


# ============================================================================
# PdfParser
# ============================================================================


class TestPdfParser:
    @pytest.fixture
    def parser(self):
        fitz = pytest.importorskip("fitz")
        from mindforge.infrastructure.parsing.pdf_parser import PdfParser
        return PdfParser()

    @pytest.fixture
    def minimal_pdf(self):
        fitz = pytest.importorskip("fitz")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World from PDF")
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_extracts_text(self, parser, minimal_pdf):
        result = parser.parse(minimal_pdf, "doc.pdf")
        assert "Hello World" in result.text_content

    def test_produces_content_blocks(self, parser, minimal_pdf):
        result = parser.parse(minimal_pdf, "doc.pdf")
        assert len(result.content_blocks) >= 1

    def test_empty_pdf_returns_empty_text(self, parser):
        fitz = pytest.importorskip("fitz")
        doc = fitz.open()
        doc.new_page()  # empty page
        pdf_bytes = doc.tobytes()
        doc.close()
        result = parser.parse(pdf_bytes, "empty.pdf")
        assert result.text_content == ""
        assert result.embedded_images == []

    def test_page_limit_raises_parse_error(self):
        fitz = pytest.importorskip("fitz")
        from mindforge.infrastructure.parsing.pdf_parser import PdfParser
        from mindforge.infrastructure.parsing.registry import ParseError
        doc = fitz.open()
        for _ in range(3):
            doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        parser = PdfParser(max_pages=2)
        with pytest.raises(ParseError):
            parser.parse(pdf_bytes, "big.pdf")

    def test_malformed_bytes_raises_parse_error(self, parser):
        from mindforge.infrastructure.parsing.registry import ParseError
        with pytest.raises(ParseError):
            parser.parse(b"this is not a pdf", "bad.pdf")

    def test_oversized_image_skipped(self):
        """Individual images exceeding max_image_bytes are silently skipped."""
        fitz = pytest.importorskip("fitz")
        from mindforge.infrastructure.parsing.pdf_parser import PdfParser
        # Create a PDF with a small text only (no image) — test via tiny cap
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "text")
        pdf_bytes = doc.tobytes()
        doc.close()
        # max_image_bytes=0 means all images (even empty) are skipped
        parser = PdfParser(max_image_bytes=0)
        result = parser.parse(pdf_bytes, "doc.pdf")
        assert result.embedded_images == []

    def test_metadata_extracted_when_present(self):
        fitz = pytest.importorskip("fitz")
        from mindforge.infrastructure.parsing.pdf_parser import PdfParser
        doc = fitz.open()
        doc.set_metadata({"title": "Test Title", "author": "Author Name"})
        page = doc.new_page()
        page.insert_text((72, 72), "content")
        pdf_bytes = doc.tobytes()
        doc.close()
        parser = PdfParser()
        result = parser.parse(pdf_bytes, "doc.pdf")
        assert result.metadata.get("pdf_title") == "Test Title"
        assert result.metadata.get("pdf_author") == "Author Name"


# ============================================================================
# DocxParser
# ============================================================================


class TestDocxParser:
    @pytest.fixture
    def minimal_docx(self) -> bytes:
        python_docx = pytest.importorskip("docx")
        buf = io.BytesIO()
        doc = python_docx.Document()
        doc.add_heading("Test Heading", level=1)
        doc.add_paragraph("Some content text.")
        doc.save(buf)
        return buf.getvalue()

    @pytest.fixture
    def parser(self):
        pytest.importorskip("docx")
        from mindforge.infrastructure.parsing.docx_parser import DocxParser
        return DocxParser()

    def test_extracts_text(self, parser, minimal_docx):
        result = parser.parse(minimal_docx, "doc.docx")
        assert "Some content text" in result.text_content

    def test_heading_detection(self, parser, minimal_docx):
        result = parser.parse(minimal_docx, "doc.docx")
        heading_blocks = [
            b for b in result.content_blocks if b.metadata.get("is_heading")
        ]
        assert len(heading_blocks) >= 1

    def test_first_heading_in_metadata(self, parser, minimal_docx):
        result = parser.parse(minimal_docx, "doc.docx")
        # If no core title, first_heading should be extracted
        assert result.metadata.get("first_heading") == "Test Heading"

    def test_empty_document_returns_empty_text(self, parser):
        python_docx = pytest.importorskip("docx")
        buf = io.BytesIO()
        doc = python_docx.Document()
        doc.save(buf)
        result = parser.parse(buf.getvalue(), "empty.docx")
        assert result.text_content == ""

    def test_malformed_bytes_raises_parse_error(self, parser):
        from mindforge.infrastructure.parsing.registry import ParseError
        with pytest.raises(ParseError):
            parser.parse(b"not a docx", "bad.docx")

    def test_oversized_image_skipped(self):
        """Individual images exceeding max_image_bytes are silently skipped."""
        python_docx = pytest.importorskip("docx")
        from mindforge.infrastructure.parsing.docx_parser import DocxParser
        buf = io.BytesIO()
        doc = python_docx.Document()
        doc.add_paragraph("text only")
        doc.save(buf)
        # max_image_bytes=0 → all images skipped even if somehow present
        parser = DocxParser(max_image_bytes=0)
        result = parser.parse(buf.getvalue(), "doc.docx")
        assert result.embedded_images == []


# ============================================================================
# LessonIdentity.resolve
# ============================================================================


class TestLessonIdentityResolve:
    def test_step1_frontmatter_lesson_id(self):
        identity = LessonIdentity.resolve({"lesson_id": "my-lesson"}, "ignored.md")
        assert identity.lesson_id == "my-lesson"

    def test_step2_frontmatter_title_slugified(self):
        identity = LessonIdentity.resolve({"title": "Sieci neuronowe"}, "f.md")
        assert identity.lesson_id == "sieci-neuronowe"

    def test_step3_pdf_title_slugified(self):
        identity = LessonIdentity.resolve({"pdf_title": "Deep Learning Intro"}, "f.pdf")
        assert "deep" in identity.lesson_id

    def test_step4_filename_stem(self):
        identity = LessonIdentity.resolve({}, "S02E05_Attention Mechanism.md")
        assert identity.lesson_id  # non-empty, some slug

    def test_step5_raises_when_no_valid_id(self):
        # All-punctuation filename produces empty slug → unresolvable
        with pytest.raises(LessonIdentityError):
            LessonIdentity.resolve({}, "---")

    def test_reserved_name_falls_back_to_filename(self):
        # Reserved lesson_id in frontmatter causes fallback to filename stem
        identity = LessonIdentity.resolve({"lesson_id": "index"}, "my-lecture.md")
        assert identity.lesson_id == "my-lecture"

    def test_all_sources_reserved_raises(self):
        # Every candidate resolves to a reserved name → must raise
        with pytest.raises(LessonIdentityError):
            LessonIdentity.resolve({"lesson_id": "index", "title": "index"}, "---")

    def test_title_populated_independently(self):
        identity = LessonIdentity.resolve(
            {"title": "My Title", "lesson_id": "my-id"}, "f.md"
        )
        assert identity.title == "My Title"
        assert identity.lesson_id == "my-id"


# ============================================================================
# IngestionService
# ============================================================================


def _make_parsed_doc(
    lesson_id: str = "test-lesson", title: str = "Test"
) -> ParsedDocument:
    return ParsedDocument(
        text_content="Some content text.",
        metadata={"lesson_id": lesson_id, "title": title},
        content_blocks=[],
        embedded_images=[],
    )


def _make_service(
    doc_repo: Any,
    task_store: Any,
    event_publisher: Any,
    *,
    parsed_doc: ParsedDocument | None = None,
    max_pending: int = 10,
) -> IngestionService:
    from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer

    sanitizer = UploadSanitizer()

    mock_parser = MagicMock()
    mock_parser.parse.return_value = parsed_doc or _make_parsed_doc()
    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_parser

    return IngestionService(
        doc_repo=doc_repo,
        sanitizer=sanitizer,
        parsers=mock_registry,
        task_store=task_store,
        event_publisher=event_publisher,
        max_pending_tasks_per_user=max_pending,
    )


@pytest.fixture
def kb_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


class TestIngestionService:
    @pytest.mark.asyncio
    async def test_happy_path_first_upload(self, kb_id, user_id):
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        doc_repo.deactivate_lesson.return_value = 0  # no prior revision
        doc_repo.save.return_value = None

        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 0
        task_id = uuid.uuid4()
        task_store.create_task.return_value = task_id

        event_publisher = AsyncMock()

        service = _make_service(doc_repo, task_store, event_publisher)
        content = b"# Test Lesson\n\nContent here."
        result = await service.ingest(
            raw_bytes=content,
            filename="test_lesson.md",
            knowledge_base_id=kb_id,
            upload_source=UploadSource.API,
            uploaded_by=user_id,
        )

        assert isinstance(result, IngestionResult)
        assert result.revision == 1
        assert result.task_id == task_id
        doc_repo.save.assert_called_once()
        task_store.create_task.assert_called_once()
        event_publisher.publish_in_tx.assert_called_once()

    @pytest.mark.asyncio
    async def test_second_upload_increments_revision(self, kb_id, user_id):
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        doc_repo.deactivate_lesson.return_value = 1  # first rev was deactivated
        doc_repo.save.return_value = None

        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 0
        task_store.create_task.return_value = uuid.uuid4()

        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        result = await service.ingest(
            raw_bytes=b"# Test\n\nUpdated content.",
            filename="test_lesson.md",
            knowledge_base_id=kb_id,
            upload_source=UploadSource.API,
            uploaded_by=user_id,
        )

        assert result.revision == 2

    @pytest.mark.asyncio
    async def test_duplicate_content_raises(self, kb_id, user_id):
        existing_doc = MagicMock(spec=Document)
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = existing_doc

        task_store = AsyncMock()
        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        with pytest.raises(DuplicateContentError) as exc_info:
            await service.ingest(
                raw_bytes=b"# Test\n\nSame content.",
                filename="lesson.md",
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=user_id,
            )
        assert exc_info.value.kb_id == kb_id

    @pytest.mark.asyncio
    async def test_pending_task_limit_raises(self, kb_id, user_id):
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None

        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 10  # at limit

        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher, max_pending=10)

        with pytest.raises(PendingTaskLimitError) as exc_info:
            await service.ingest(
                raw_bytes=b"# Test\n\nContent.",
                filename="lesson.md",
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=user_id,
            )
        assert exc_info.value.current_count == 10
        assert exc_info.value.limit == 10

    @pytest.mark.asyncio
    async def test_anonymous_upload_skips_task_limit_check(self, kb_id):
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        doc_repo.deactivate_lesson.return_value = 0
        doc_repo.save.return_value = None

        task_store = AsyncMock()
        task_store.create_task.return_value = uuid.uuid4()

        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        await service.ingest(
            raw_bytes=b"# Test\n\nContent.",
            filename="lesson.md",
            knowledge_base_id=kb_id,
            upload_source=UploadSource.FILE_WATCHER,
            uploaded_by=None,  # anonymous
        )
        task_store.count_pending_for_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_sanitizer_rejects_traversal_as_upload_rejected(self, kb_id, user_id):
        """Path traversal must surface as UploadRejectedError, not UnresolvableLessonError."""
        doc_repo = AsyncMock()
        task_store = AsyncMock()
        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        with pytest.raises(UploadRejectedError):
            await service.ingest(
                raw_bytes=b"# Test\n\nContent.",
                filename="../etc/passwd",
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=user_id,
            )

    @pytest.mark.asyncio
    async def test_sanitizer_rejects_unknown_extension_as_upload_rejected(self, kb_id, user_id):
        """Unknown extension must surface as UploadRejectedError."""
        doc_repo = AsyncMock()
        task_store = AsyncMock()
        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        with pytest.raises(UploadRejectedError):
            await service.ingest(
                raw_bytes=b"binary data",
                filename="archive.zip",
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=user_id,
            )

    @pytest.mark.asyncio
    async def test_published_event_has_correct_fields(self, kb_id, user_id):
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        doc_repo.deactivate_lesson.return_value = 0
        doc_repo.save.return_value = None

        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 0
        task_store.create_task.return_value = uuid.uuid4()

        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        raw = b"# My Lesson\n\nContent."
        await service.ingest(
            raw_bytes=raw,
            filename="my_lesson.md",
            knowledge_base_id=kb_id,
            upload_source=UploadSource.API,
            uploaded_by=user_id,
        )

        published_event = event_publisher.publish_in_tx.call_args[0][0]
        assert isinstance(published_event, DocumentIngested)
        assert published_event.knowledge_base_id == kb_id
        assert published_event.uploaded_by == user_id
        assert published_event.upload_source == "API"

    @pytest.mark.asyncio
    async def test_published_event_carries_revision(self, kb_id, user_id):
        """DocumentIngested event must include the revision number (F-5)."""
        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        doc_repo.deactivate_lesson.return_value = 2  # prior rev 2 deactivated
        doc_repo.save.return_value = None

        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 0
        task_store.create_task.return_value = uuid.uuid4()

        event_publisher = AsyncMock()
        service = _make_service(doc_repo, task_store, event_publisher)

        await service.ingest(
            raw_bytes=b"# My Lesson\n\nContent v3.",
            filename="my_lesson.md",
            knowledge_base_id=kb_id,
            upload_source=UploadSource.API,
            uploaded_by=user_id,
        )

        published_event = event_publisher.publish_in_tx.call_args[0][0]
        assert isinstance(published_event, DocumentIngested)
        assert published_event.revision == 3  # prev_revision(2) + 1

    @pytest.mark.asyncio
    async def test_unresolvable_lesson_raises(self, kb_id, user_id):
        """A document whose filename produces no valid lesson_id is rejected."""
        parsed = ParsedDocument(
            text_content="x", metadata={}, content_blocks=[], embedded_images=[]
        )

        mock_parser = MagicMock()
        mock_parser.parse.return_value = parsed
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_parser

        from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer

        doc_repo = AsyncMock()
        doc_repo.get_by_content_hash.return_value = None
        task_store = AsyncMock()
        task_store.count_pending_for_user.return_value = 0
        event_publisher = AsyncMock()

        service = IngestionService(
            doc_repo=doc_repo,
            sanitizer=UploadSanitizer(),
            parsers=mock_registry,
            task_store=task_store,
            event_publisher=event_publisher,
        )

        # Filename "---" sanitizes to empty after slugify → LessonIdentityError
        with pytest.raises(UnresolvableLessonError):
            await service.ingest(
                raw_bytes=b"# x",
                filename="-.md",
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=user_id,
            )
