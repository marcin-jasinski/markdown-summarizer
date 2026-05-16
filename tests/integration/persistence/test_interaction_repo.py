"""
Integration tests: interaction redaction policy via PostgresInteractionStore.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from mindforge.infrastructure.persistence.interaction_repo import (
    PostgresInteractionStore,
)

pytestmark = pytest.mark.asyncio


async def _create_user(session) -> uuid.UUID:
    from mindforge.infrastructure.persistence.models import UserModel

    u = UserModel(display_name="Test", created_at=datetime.now(timezone.utc))
    session.add(u)
    await session.flush()
    return u.user_id


@pytest.mark.integration
async def test_create_and_get_interaction(session):
    user_id = await _create_user(session)
    store = PostgresInteractionStore(session)

    iid = await store.create_interaction(
        interaction_type="quiz_session",
        user_id=user_id,
        context={"kb_id": "some-kb"},
    )
    fetched = await store.get_interaction(iid)

    assert fetched is not None
    assert fetched.interaction_id == iid
    assert fetched.interaction_type == "quiz_session"


@pytest.mark.integration
async def test_add_turn(session):
    user_id = await _create_user(session)
    store = PostgresInteractionStore(session)

    iid = await store.create_interaction(
        interaction_type="quiz_session", user_id=user_id
    )
    await store.add_turn(
        iid,
        actor_type="user",
        actor_id=str(user_id),
        action="answer",
        input_data={"question": "What is Python?"},
        output_data={
            "answer": "A language",
            "reference_answer": "SECRET",
            "grounding_context": "CONTEXT",
            "raw_prompt": "PROMPT",
            "raw_completion": "COMPLETION",
            "score": 0.9,
        },
        cost=0.001,
    )

    interaction = await store.get_interaction(iid)
    assert len(interaction.turns) == 1


@pytest.mark.integration
async def test_list_for_user_redacts_sensitive_fields(session):
    """output_data must have sensitive fields stripped in user-facing list."""
    user_id = await _create_user(session)
    store = PostgresInteractionStore(session)

    iid = await store.create_interaction(
        interaction_type="quiz_session", user_id=user_id
    )
    await store.add_turn(
        iid,
        actor_type="agent",
        actor_id="system",
        action="evaluate",
        output_data={
            "score": 0.8,
            "reference_answer": "DO NOT EXPOSE",
            "grounding_context": "DO NOT EXPOSE",
            "raw_prompt": "DO NOT EXPOSE",
            "raw_completion": "DO NOT EXPOSE",
        },
    )

    interactions = await store.list_for_user(user_id)
    assert len(interactions) >= 1

    found = next(i for i in interactions if i.interaction_id == iid)
    for turn in found.turns:
        od = turn.output_data
        assert "reference_answer" not in od
        assert "grounding_context" not in od
        assert "raw_prompt" not in od
        assert "raw_completion" not in od
        assert od.get("score") == 0.8  # non-sensitive field kept


@pytest.mark.integration
async def test_list_unredacted_returns_all_fields(session):
    """Admin endpoint must return full unredacted data."""
    user_id = await _create_user(session)
    store = PostgresInteractionStore(session)

    iid = await store.create_interaction(
        interaction_type="quiz_session", user_id=user_id
    )
    await store.add_turn(
        iid,
        actor_type="agent",
        actor_id="system",
        action="evaluate",
        output_data={
            "score": 0.8,
            "reference_answer": "VISIBLE TO ADMIN",
        },
    )

    interactions = await store.list_unredacted()
    found = next((i for i in interactions if i.interaction_id == iid), None)
    assert found is not None
    for turn in found.turns:
        assert turn.output_data.get("reference_answer") == "VISIBLE TO ADMIN"
