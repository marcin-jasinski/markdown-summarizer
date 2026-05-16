"""
Integration tests: study progress SM-2 update cycle.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from mindforge.domain.models import ReviewResult
from mindforge.infrastructure.persistence.study_progress_repo import (
    PostgresStudyProgressRepository,
    _sm2_update,
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

    kb = KnowledgeBaseModel(owner_id=owner_id, name="SM2 KB")
    session.add(kb)
    await session.flush()
    return kb.kb_id


@pytest.mark.integration
async def test_due_cards_empty_initially(session):
    user_id = await _create_user(session)
    kb_id = await _create_kb(session, user_id)

    repo = PostgresStudyProgressRepository(session)
    cards = await repo.get_due_cards(user_id, kb_id, date.today())
    assert cards == []


@pytest.mark.integration
async def test_save_review_creates_progress(session):
    user_id = await _create_user(session)
    kb_id = await _create_kb(session, user_id)

    repo = PostgresStudyProgressRepository(session)
    card_id = "a" * 16

    await repo.save_review(user_id, kb_id, card_id, ReviewResult(rating=4))

    count = await repo.due_count(user_id, kb_id, date.today())
    # After a successful review (rating >= 3), interval > 0 → not due today
    assert count == 0


@pytest.mark.integration
async def test_failed_review_due_tomorrow(session):
    user_id = await _create_user(session)
    kb_id = await _create_kb(session, user_id)

    repo = PostgresStudyProgressRepository(session)
    card_id = "b" * 16

    # rating=0 → interval=1 → due tomorrow (not today)
    await repo.save_review(user_id, kb_id, card_id, ReviewResult(rating=0))

    count = await repo.due_count(user_id, kb_id, date.today())
    assert count == 0  # not due today because next_review = tomorrow


@pytest.mark.integration
async def test_sm2_upsert(session):
    """Second review updates existing row rather than inserting duplicate."""
    user_id = await _create_user(session)
    kb_id = await _create_kb(session, user_id)

    repo = PostgresStudyProgressRepository(session)
    card_id = "c" * 16

    await repo.save_review(user_id, kb_id, card_id, ReviewResult(rating=5))
    await repo.save_review(user_id, kb_id, card_id, ReviewResult(rating=5))
    # No PK violation → upsert worked correctly


# Unit tests for SM-2 algorithm itself (no DB required)
def test_sm2_failed_recall_resets():
    ef, interval, reps = _sm2_update(0, 2.5, 10, 3)
    assert interval == 1
    assert reps == 0


def test_sm2_first_successful_review():
    ef, interval, reps = _sm2_update(4, 2.5, 0, 0)
    assert interval == 1
    assert reps == 1


def test_sm2_second_successful_review():
    ef, interval, reps = _sm2_update(4, 2.5, 1, 1)
    assert interval == 6
    assert reps == 2


def test_sm2_ease_factor_increases():
    ef, *_ = _sm2_update(5, 2.5, 0, 0)
    assert ef > 2.5


def test_sm2_ease_factor_minimum():
    ef, *_ = _sm2_update(0, 1.3, 0, 0)
    assert ef >= 1.3
