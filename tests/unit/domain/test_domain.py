"""
Unit tests for the domain layer.

Tests cover all validation logic, deterministic computations, and
serialization.  No I/O, no network — pure Python only.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from mindforge.domain.events import (
    DocumentIngested,
    ProcessingCompleted,
)
from mindforge.domain.models import (
    CardType,
    ContentHash,
    FlashcardData,
    LessonIdentity,
    LessonIdentityError,
    StepFingerprint,
    TokenBudget,
    slugify,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc)
_KB_ID = uuid4()
_DOC_ID = uuid4()


# ---------------------------------------------------------------------------
# 1.5.1 — LessonIdentity.resolve()
# ---------------------------------------------------------------------------


class TestLessonIdentityResolve:
    def test_step1_frontmatter_lesson_id(self):
        identity = LessonIdentity.resolve({"lesson_id": "my-lesson"}, "whatever.md")
        assert identity.lesson_id == "my-lesson"

    def test_step1_frontmatter_lesson_id_with_underscores(self):
        identity = LessonIdentity.resolve({"lesson_id": "lesson_01"}, "whatever.md")
        assert identity.lesson_id == "lesson_01"

    def test_step1_invalid_falls_through_to_step2(self):
        """Uppercase lesson_id fails validation; step 2 (title) is used."""
        identity = LessonIdentity.resolve(
            {"lesson_id": "INVALID", "title": "Valid Title"},
            "whatever.md",
        )
        assert identity.lesson_id == "valid-title"

    def test_step2_frontmatter_title_slugified(self):
        identity = LessonIdentity.resolve(
            {"title": "Sieci neuronowe — wprowadzenie"}, "doc.md"
        )
        assert identity.lesson_id == "sieci-neuronowe-wprowadzenie"

    def test_step2_polish_characters_normalized(self):
        identity = LessonIdentity.resolve(
            {"title": "Uczenie maszynowe: Część 1"}, "doc.md"
        )
        # ę → e, ć → c, ś → s via ASCII normalization
        assert identity.lesson_id == "uczenie-maszynowe-czesc-1"

    def test_step3_pdf_title(self):
        identity = LessonIdentity.resolve(
            {"pdf_title": "Attention Mechanism"}, "doc.pdf"
        )
        assert identity.lesson_id == "attention-mechanism"

    def test_step4_filename_stem(self):
        identity = LessonIdentity.resolve({}, "S02E05_Attention Mechanism.md")
        assert identity.lesson_id == "s02e05_attention-mechanism"

    def test_step4_filename_no_extension(self):
        identity = LessonIdentity.resolve({}, "my-lesson")
        assert identity.lesson_id == "my-lesson"

    def test_step5_raises_when_all_fail(self):
        """Empty filename produces empty slug → LessonIdentityError."""
        with pytest.raises(LessonIdentityError):
            LessonIdentity.resolve({}, "!!!")

    def test_max_length_80_accepted(self):
        long_id = "a" * 80
        identity = LessonIdentity.resolve({"lesson_id": long_id}, "x.md")
        assert len(identity.lesson_id) == 80

    def test_max_length_81_rejected_falls_through(self):
        """lesson_id > 80 chars fails step 1; step 2 title is used."""
        over_limit = "a" * 81
        identity = LessonIdentity.resolve(
            {"lesson_id": over_limit, "title": "short"}, "x.md"
        )
        assert identity.lesson_id == "short"

    def test_reserved_name_index_rejected(self):
        """Reserved name 'index' fails validation; falls to next step."""
        identity = LessonIdentity.resolve(
            {"lesson_id": "index", "title": "Valid"}, "x.md"
        )
        assert identity.lesson_id == "valid"

    def test_reserved_name_default_rejected(self):
        identity = LessonIdentity.resolve(
            {"lesson_id": "default", "title": "OK"}, "x.md"
        )
        assert identity.lesson_id == "ok"

    def test_reserved_name_init_rejected(self):
        identity = LessonIdentity.resolve(
            {"lesson_id": "__init__", "title": "fine"}, "x.md"
        )
        assert identity.lesson_id == "fine"

    def test_title_resolution_uses_frontmatter_title(self):
        identity = LessonIdentity.resolve(
            {"lesson_id": "slug", "title": "My Display Title"}, "x.md"
        )
        assert identity.title == "My Display Title"

    def test_title_resolution_falls_back_to_filename(self):
        identity = LessonIdentity.resolve({}, "some-file.md")
        assert identity.title == "some-file"

    def test_empty_after_sanitization_raises(self):
        """A filename that produces empty slug after sanitization → error."""
        with pytest.raises(LessonIdentityError):
            LessonIdentity.resolve({}, ".md")

    def test_digits_only_accepted(self):
        identity = LessonIdentity.resolve({"lesson_id": "123"}, "x.md")
        assert identity.lesson_id == "123"


# ---------------------------------------------------------------------------
# 1.5.2 — ContentHash.compute()
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_compute_returns_sha256_hex(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        ch = ContentHash.compute(data)
        assert ch.sha256 == expected

    def test_different_bytes_different_hash(self):
        ch1 = ContentHash.compute(b"hello")
        ch2 = ContentHash.compute(b"world")
        assert ch1.sha256 != ch2.sha256

    def test_same_bytes_same_hash(self):
        data = b"reproducible"
        assert ContentHash.compute(data) == ContentHash.compute(data)

    def test_empty_bytes(self):
        ch = ContentHash.compute(b"")
        assert len(ch.sha256) == 64  # 256-bit → 64 hex chars

    def test_frozen(self):
        ch = ContentHash.compute(b"x")
        with pytest.raises((AttributeError, TypeError)):
            ch.sha256 = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 1.5.3 — FlashcardData card_id determinism
# ---------------------------------------------------------------------------


class TestFlashcardCardId:
    def _make_card(self, kb_id: UUID = _KB_ID, **overrides: Any) -> FlashcardData:
        defaults = dict(
            kb_id=kb_id,
            lesson_id="lesson-1",
            card_type=CardType.BASIC,
            front="What is backpropagation?",
            back="An algorithm for training neural networks.",
        )
        defaults.update(overrides)
        return FlashcardData(**defaults)  # type: ignore[arg-type]

    def test_same_inputs_produce_same_card_id(self):
        c1 = self._make_card()
        c2 = self._make_card()
        assert c1.card_id == c2.card_id

    def test_different_kb_id_produces_different_card_id(self):
        c1 = self._make_card(kb_id=uuid4())
        c2 = self._make_card(kb_id=uuid4())
        assert c1.card_id != c2.card_id

    def test_different_lesson_id_produces_different_card_id(self):
        c1 = self._make_card(lesson_id="lesson-a")
        c2 = self._make_card(lesson_id="lesson-b")
        assert c1.card_id != c2.card_id

    def test_different_front_produces_different_card_id(self):
        c1 = self._make_card(front="Q1")
        c2 = self._make_card(front="Q2")
        assert c1.card_id != c2.card_id

    def test_card_id_length_is_16_chars(self):
        c = self._make_card()
        assert len(c.card_id) == 16

    def test_different_card_type_produces_different_card_id(self):
        c1 = self._make_card(card_type=CardType.BASIC)
        c2 = self._make_card(card_type=CardType.CLOZE)
        assert c1.card_id != c2.card_id

    def test_card_id_is_hex_string(self):
        c = self._make_card()
        int(c.card_id, 16)  # no exception → valid hex


# ---------------------------------------------------------------------------
# 1.5.4 — StepFingerprint.compute()
# ---------------------------------------------------------------------------


class TestStepFingerprint:
    def _make(self, **overrides: Any) -> StepFingerprint:
        defaults = dict(
            input_hash="abc123",
            prompt_version="v1",
            model_id="gpt-4o-mini",
            agent_version="1.0.0",
        )
        defaults.update(overrides)
        return StepFingerprint(**defaults)  # type: ignore[arg-type]

    def test_same_inputs_same_hash(self):
        fp1 = self._make()
        fp2 = self._make()
        assert fp1.compute() == fp2.compute()

    def test_different_input_hash_different_result(self):
        fp1 = self._make(input_hash="aaa")
        fp2 = self._make(input_hash="bbb")
        assert fp1.compute() != fp2.compute()

    def test_different_prompt_version_different_result(self):
        fp1 = self._make(prompt_version="v1")
        fp2 = self._make(prompt_version="v2")
        assert fp1.compute() != fp2.compute()

    def test_different_model_id_different_result(self):
        fp1 = self._make(model_id="gpt-4o-mini")
        fp2 = self._make(model_id="claude-3-haiku")
        assert fp1.compute() != fp2.compute()

    def test_different_agent_version_different_result(self):
        fp1 = self._make(agent_version="1.0.0")
        fp2 = self._make(agent_version="1.0.1")
        assert fp1.compute() != fp2.compute()

    def test_result_length_is_16_chars(self):
        fp = self._make()
        assert len(fp.compute()) == 16

    def test_frozen(self):
        fp = self._make()
        with pytest.raises((AttributeError, TypeError)):
            fp.input_hash = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 1.5.5 — DomainEvent.to_dict()
# ---------------------------------------------------------------------------


class TestDomainEventToDict:
    def test_event_type_included(self):
        event = ProcessingCompleted(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            lesson_id="lesson-1",
            timestamp=_NOW,
        )
        d = event.to_dict()
        assert d["event_type"] == "ProcessingCompleted"

    def test_uuid_serialized_as_string(self):
        event = ProcessingCompleted(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            lesson_id="lesson-1",
            timestamp=_NOW,
        )
        d = event.to_dict()
        assert d["document_id"] == str(_DOC_ID)
        assert isinstance(d["document_id"], str)

    def test_datetime_serialized_as_iso_string(self):
        event = ProcessingCompleted(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            lesson_id="lesson-1",
            timestamp=_NOW,
        )
        d = event.to_dict()
        assert d["timestamp"] == _NOW.isoformat()

    def test_none_uuid_serialized(self):
        event = DocumentIngested(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            lesson_id="test",
            upload_source="API",
            content_sha256="abc",
            uploaded_by=None,
            timestamp=_NOW,
        )
        d = event.to_dict()
        assert d["uploaded_by"] is None

    def test_all_fields_present(self):
        event = ProcessingCompleted(
            document_id=_DOC_ID,
            knowledge_base_id=_KB_ID,
            lesson_id="lesson-1",
            timestamp=_NOW,
        )
        d = event.to_dict()
        assert "document_id" in d
        assert "knowledge_base_id" in d
        assert "lesson_id" in d
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# 1.5.6 — TokenBudget.available_for_context
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def test_available_for_context_basic(self):
        budget = TokenBudget(total_tokens=4096, system_tokens=512, query_tokens=128)
        assert budget.available_for_context == 4096 - 512 - 128

    def test_never_negative(self):
        budget = TokenBudget(total_tokens=100, system_tokens=80, query_tokens=50)
        assert budget.available_for_context == 0

    def test_zero_overhead(self):
        budget = TokenBudget(total_tokens=1000, system_tokens=0, query_tokens=0)
        assert budget.available_for_context == 1000

    def test_exact_boundary(self):
        budget = TokenBudget(total_tokens=200, system_tokens=100, query_tokens=100)
        assert budget.available_for_context == 0


# ---------------------------------------------------------------------------
# Slugify helper tests
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Część 1: Wprowadzenie") == "czesc-1-wprowadzenie"

    def test_multiple_hyphens_collapsed(self):
        assert slugify("a  b   c") == "a-b-c"

    def test_strips_leading_trailing_hyphens(self):
        assert slugify("  hello  ") == "hello"

    def test_dashes_preserved(self):
        result = slugify("already-slugged")
        assert result == "already-slugged"

    def test_underscores_preserved(self):
        result = slugify("has_underscores")
        assert result == "has_underscores"
