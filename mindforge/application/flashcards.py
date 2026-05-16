"""
Application layer — Flashcard Service.

Manages the flashcard catalog and spaced-repetition review scheduling.

The SM-2 algorithm lives in ``mindforge.domain.models.sm2_update`` (pure
domain logic, zero I/O).  This service joins card content from
:class:`~mindforge.domain.ports.ArtifactRepository` with SM-2 scheduling
state from :class:`~mindforge.domain.ports.StudyProgressStore`.
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from mindforge.domain.models import CardState, FlashcardData, ReviewResult
from mindforge.domain.ports import ArtifactRepository, StudyProgressStore

log = logging.getLogger(__name__)


class FlashcardService:
    """Manages the flashcard catalog and spaced-repetition scheduling.

    Parameters
    ----------
    artifact_repo:
        Artifact repository — provides card content (front, back, card_type,
        lesson_id) from processed :class:`~mindforge.domain.models.DocumentArtifact`
        objects.
    study_progress:
        Study-progress store — provides SM-2 scheduling state (ease_factor,
        interval, next_review, repetitions).
    """

    def __init__(
        self,
        artifact_repo: ArtifactRepository,
        study_progress: StudyProgressStore,
    ) -> None:
        self._artifacts = artifact_repo
        self._progress = study_progress

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_due_cards(self, user_id: UUID, kb_id: UUID) -> list[CardState]:
        """Return cards due for review today, populated with flashcard content.

        Combines two card populations:

        1. **Reviewed cards due today** — joined from *study_progress* (SM-2
           state) with artifact content.
        2. **New, never-reviewed cards** — every flashcard present in the KB's
           latest active artifacts that has no ``study_progress`` row yet.
           These are surfaced with default SM-2 state (ease 2.5, interval 0,
           repetitions 0, ``next_review`` = today) so they are immediately
           studyable.

        Without (2) a brand-new user with freshly generated cards would see
        an empty deck because no ``study_progress`` row exists until after
        the first review — which was the original "flashcards don't work"
        defect.
        """
        today = date.today()
        due_states = await self._progress.get_due_cards(user_id, kb_id, today)
        all_cards = await self._artifacts.list_flashcards_for_kb(kb_id)

        if not due_states and not all_cards:
            return []

        card_index: dict[str, FlashcardData] = {c.card_id: c for c in all_cards}
        scheduled_ids: set[str] = {state.card_id for state in due_states}

        populated: list[CardState] = []

        # 1. Reviewed cards that are due today — join with artifact content.
        for state in due_states:
            card_data = card_index.get(state.card_id)
            if card_data is not None:
                populated.append(
                    CardState(
                        card_id=state.card_id,
                        kb_id=state.kb_id,
                        lesson_id=card_data.lesson_id,
                        card_type=card_data.card_type,
                        front=card_data.front,
                        back=card_data.back,
                        next_review=state.next_review,
                        interval=state.interval,
                        ease_factor=state.ease_factor,
                        repetitions=state.repetitions,
                    )
                )
            else:
                # Card content no longer in artifacts — include state as-is.
                populated.append(state)

        # 2. Brand-new, never-reviewed cards — synthesize default SM-2 state.
        for card in all_cards:
            if card.card_id in scheduled_ids:
                continue
            populated.append(
                CardState(
                    card_id=card.card_id,
                    kb_id=kb_id,
                    lesson_id=card.lesson_id,
                    card_type=card.card_type,
                    front=card.front,
                    back=card.back,
                    next_review=today,
                    interval=0,
                    ease_factor=2.5,
                    repetitions=0,
                )
            )

        return populated

    async def review_card(
        self,
        user_id: UUID,
        kb_id: UUID,
        card_id: str,
        result: ReviewResult,
    ) -> None:
        """Apply SM-2 update for a card review and persist the new schedule.

        The SM-2 algorithm itself runs inside
        ``StudyProgressStore.save_review()`` in the infrastructure layer.
        """
        await self._progress.save_review(user_id, kb_id, card_id, result)

    async def list_all_cards(
        self,
        kb_id: UUID,
        lesson_id: str | None = None,
    ) -> list[FlashcardData]:
        """Return all flashcards in the KB, optionally filtered by lesson.

        Returns raw :class:`~mindforge.domain.models.FlashcardData` objects
        from the latest active artifact per document.  Does not include
        SM-2 scheduling state (use :meth:`get_due_cards` for that).
        """
        return await self._artifacts.list_flashcards_for_kb(kb_id, lesson_id)

    async def due_count(self, user_id: UUID, kb_id: UUID) -> int:
        """Return the number of cards due for review today.

        Includes both scheduled-and-due cards and brand-new (never-reviewed)
        cards, mirroring :meth:`get_due_cards`.
        """
        cards = await self.get_due_cards(user_id, kb_id)
        return len(cards)
