"""
Unit tests for Phase 10 — Flashcard Service.

Covers:
  10.5.1  SM-2 calculations with various rating inputs
  10.5.4  Flashcard due-date calculations
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from mindforge.application.flashcards import FlashcardService
from mindforge.domain.models import (
    CardState,
    CardType,
    FlashcardData,
    ReviewResult,
    sm2_update,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    artifact_repo=None,
    study_progress=None,
) -> FlashcardService:
    return FlashcardService(
        artifact_repo=artifact_repo or AsyncMock(),
        study_progress=study_progress or AsyncMock(),
    )


def _make_flashcard(
    kb_id: UUID,
    lesson_id: str = "python-basics",
    card_type: CardType = CardType.BASIC,
    front: str = "What is a variable?",
    back: str = "A named storage location",
) -> FlashcardData:
    return FlashcardData(
        kb_id=kb_id,
        lesson_id=lesson_id,
        card_type=card_type,
        front=front,
        back=back,
    )


def _make_card_state(
    card_id: str,
    kb_id: UUID,
    lesson_id: str = "",  # empty until joined
    next_review: date | None = None,
    ease_factor: float = 2.5,
    interval: int = 1,
    repetitions: int = 0,
) -> CardState:
    return CardState(
        card_id=card_id,
        kb_id=kb_id,
        lesson_id=lesson_id,
        card_type=CardType.BASIC,
        front="",
        back="",
        next_review=next_review or date.today(),
        interval=interval,
        ease_factor=ease_factor,
        repetitions=repetitions,
    )


# ---------------------------------------------------------------------------
# get_due_cards
# ---------------------------------------------------------------------------


class TestGetDueCards:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_due_cards_and_no_artifact_cards(self):
        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = []
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = []

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        result = await service.get_due_cards(uuid4(), uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_unreviewed_cards_in_artifacts_are_returned_as_due(self):
        """Brand-new flashcards (no study_progress row yet) must surface as due.

        Regression for the "flashcards don't work at all" bug: a fresh user
        with newly-generated cards should immediately see them.
        """
        kb_id = uuid4()
        cards = [
            _make_flashcard(kb_id, front="Q1", back="A1", lesson_id="l1"),
            _make_flashcard(kb_id, front="Q2", back="A2", lesson_id="l2"),
        ]
        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = []  # no reviews yet
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = cards

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        result = await service.get_due_cards(uuid4(), kb_id)

        assert len(result) == 2
        fronts = {r.front for r in result}
        assert fronts == {"Q1", "Q2"}
        # Default SM-2 state for new cards.
        for r in result:
            assert r.ease_factor == 2.5
            assert r.interval == 0
            assert r.repetitions == 0
            assert r.next_review == date.today()

    @pytest.mark.asyncio
    async def test_combines_scheduled_and_new_cards_without_duplicates(self):
        kb_id = uuid4()
        reviewed = _make_flashcard(kb_id, front="OLD", back="old")
        new_card = _make_flashcard(kb_id, front="NEW", back="new", lesson_id="l2")
        reviewed_state = _make_card_state(
            card_id=reviewed.card_id,
            kb_id=kb_id,
            ease_factor=1.9,
            interval=4,
            repetitions=2,
        )

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = [reviewed_state]
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = [reviewed, new_card]

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        result = await service.get_due_cards(uuid4(), kb_id)

        assert len(result) == 2
        by_front = {r.front: r for r in result}
        assert by_front["OLD"].ease_factor == 1.9
        assert by_front["OLD"].interval == 4
        assert by_front["NEW"].ease_factor == 2.5
        assert by_front["NEW"].interval == 0

    @pytest.mark.asyncio
    async def test_joins_card_content_from_artifacts(self):
        """get_due_cards populates front/back/card_type/lesson_id from artifacts."""
        kb_id = uuid4()
        card = _make_flashcard(kb_id, lesson_id="python-basics", front="Q?", back="A!")
        card_state = _make_card_state(
            card_id=card.card_id,
            kb_id=kb_id,
            next_review=date.today(),
        )

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = [card_state]

        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = [card]

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        results = await service.get_due_cards(uuid4(), kb_id)

        assert len(results) == 1
        r = results[0]
        assert r.front == "Q?"
        assert r.back == "A!"
        assert r.lesson_id == "python-basics"
        assert r.card_type == CardType.BASIC
        assert r.card_id == card.card_id

    @pytest.mark.asyncio
    async def test_sm2_state_preserved_in_join(self):
        """SM-2 fields (ease_factor, interval, repetitions) come from study_progress."""
        kb_id = uuid4()
        card = _make_flashcard(kb_id)
        card_state = _make_card_state(
            card_id=card.card_id,
            kb_id=kb_id,
            ease_factor=1.8,
            interval=14,
            repetitions=5,
        )

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = [card_state]
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = [card]

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        results = await service.get_due_cards(uuid4(), kb_id)

        assert results[0].ease_factor == 1.8
        assert results[0].interval == 14
        assert results[0].repetitions == 5

    @pytest.mark.asyncio
    async def test_graceful_when_card_missing_from_artifacts(self):
        """Cards in study_progress but not in artifacts are returned as-is (empty content)."""
        kb_id = uuid4()
        orphan_state = _make_card_state(card_id="orphan123", kb_id=kb_id)

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = [orphan_state]
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = []  # no artifact data

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        results = await service.get_due_cards(uuid4(), kb_id)

        assert len(results) == 1
        assert results[0].card_id == "orphan123"
        assert results[0].front == ""
        assert results[0].back == ""

    @pytest.mark.asyncio
    async def test_multiple_cards_all_joined(self):
        """All due cards are joined with their artifact content."""
        kb_id = uuid4()
        cards = [
            _make_flashcard(kb_id, front=f"Q{i}", back=f"A{i}", lesson_id=f"lesson-{i}")
            for i in range(3)
        ]
        states = [_make_card_state(card_id=c.card_id, kb_id=kb_id) for c in cards]

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = states
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = cards

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        results = await service.get_due_cards(uuid4(), kb_id)

        assert len(results) == 3
        fronts = {r.front for r in results}
        assert fronts == {"Q0", "Q1", "Q2"}


# ---------------------------------------------------------------------------
# review_card
# ---------------------------------------------------------------------------


class TestReviewCard:
    @pytest.mark.asyncio
    async def test_delegates_to_study_progress(self):
        """review_card calls save_review on the study progress store."""
        user_id = uuid4()
        kb_id = uuid4()
        card_id = "abc123"
        review = ReviewResult(rating=4)

        study_progress = AsyncMock()
        service = _make_service(study_progress=study_progress)
        await service.review_card(user_id, kb_id, card_id, review)

        study_progress.save_review.assert_called_once_with(
            user_id, kb_id, card_id, review
        )


# ---------------------------------------------------------------------------
# list_all_cards
# ---------------------------------------------------------------------------


class TestListAllCards:
    @pytest.mark.asyncio
    async def test_returns_all_cards_for_kb(self):
        kb_id = uuid4()
        cards = [_make_flashcard(kb_id) for _ in range(5)]
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = cards

        service = _make_service(artifact_repo=artifact_repo)
        result = await service.list_all_cards(kb_id)

        assert result == cards
        artifact_repo.list_flashcards_for_kb.assert_called_once_with(kb_id, None)

    @pytest.mark.asyncio
    async def test_filters_by_lesson_id_when_provided(self):
        kb_id = uuid4()
        target_lesson = "python-basics"
        filtered_cards = [_make_flashcard(kb_id, lesson_id=target_lesson)]

        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = filtered_cards

        service = _make_service(artifact_repo=artifact_repo)
        result = await service.list_all_cards(kb_id, lesson_id=target_lesson)

        assert result == filtered_cards
        artifact_repo.list_flashcards_for_kb.assert_called_once_with(
            kb_id, target_lesson
        )

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_kb(self):
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = []

        service = _make_service(artifact_repo=artifact_repo)
        result = await service.list_all_cards(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# due_count
# ---------------------------------------------------------------------------


class TestDueCount:
    @pytest.mark.asyncio
    async def test_counts_combined_due_and_new_cards(self):
        """due_count must mirror get_due_cards (scheduled + new)."""
        kb_id = uuid4()
        new_cards = [_make_flashcard(kb_id) for _ in range(3)]

        study_progress = AsyncMock()
        study_progress.get_due_cards.return_value = []
        artifact_repo = AsyncMock()
        artifact_repo.list_flashcards_for_kb.return_value = new_cards

        service = _make_service(
            artifact_repo=artifact_repo, study_progress=study_progress
        )
        count = await service.due_count(uuid4(), kb_id)

        assert count == 3


# ---------------------------------------------------------------------------
# SM-2 algorithm unit tests (domain model)
# ---------------------------------------------------------------------------


class TestSm2Algorithm:
    def test_failed_recall_resets_schedule(self):
        """Rating < 3 resets interval and repetitions."""
        for rating in (0, 1, 2):
            ef, interval, reps = sm2_update(
                rating=rating, ease_factor=2.5, interval=10, repetitions=5
            )
            assert interval == 1, f"rating={rating}: expected interval=1"
            assert reps == 0, f"rating={rating}: expected repetitions=0"

    def test_first_successful_recall_sets_interval_to_one(self):
        """First successful recall (repetitions=0 → 1): interval = 1."""
        ef, interval, reps = sm2_update(
            rating=3, ease_factor=2.5, interval=0, repetitions=0
        )
        assert interval == 1
        assert reps == 1

    def test_second_successful_recall_sets_interval_to_six(self):
        """Second successful recall (repetitions=1 → 2): interval = 6."""
        ef, interval, reps = sm2_update(
            rating=3, ease_factor=2.5, interval=1, repetitions=1
        )
        assert interval == 6
        assert reps == 2

    def test_subsequent_recall_scales_by_ease_factor(self):
        """After repetitions >= 2: interval = round(prev_interval * ease_factor)."""
        ef, interval, reps = sm2_update(
            rating=4, ease_factor=2.5, interval=6, repetitions=2
        )
        assert interval == round(6 * 2.5)
        assert reps == 3

    def test_ease_factor_increases_on_perfect_recall(self):
        """Rating=5 increases ease_factor."""
        ef, _, _ = sm2_update(rating=5, ease_factor=2.5, interval=1, repetitions=1)
        assert ef > 2.5

    def test_ease_factor_decreases_on_hard_recall(self):
        """Rating=3 decreases ease_factor slightly."""
        ef, _, _ = sm2_update(rating=3, ease_factor=2.5, interval=1, repetitions=1)
        assert ef < 2.5

    def test_ease_factor_floor_at_1_3(self):
        """ease_factor never drops below 1.3."""
        ef, _, _ = sm2_update(rating=0, ease_factor=1.3, interval=1, repetitions=0)
        assert ef >= 1.3

    def test_flashcard_due_date_calculation(self):
        """A card with interval=7 is next due in 7 days."""
        _, interval, _ = sm2_update(
            rating=4, ease_factor=2.5, interval=6, repetitions=2
        )
        # interval = round(6 * 2.5) = 15
        next_review = date.today() + timedelta(days=max(interval, 1))
        expected = date.today() + timedelta(days=15)
        assert next_review == expected

    def test_deterministic_for_same_inputs(self):
        """SM-2 produces the same output for the same inputs (no randomness)."""
        result1 = sm2_update(rating=4, ease_factor=2.5, interval=6, repetitions=2)
        result2 = sm2_update(rating=4, ease_factor=2.5, interval=6, repetitions=2)
        assert result1 == result2
