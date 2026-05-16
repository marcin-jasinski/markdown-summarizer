"""
Integration tests: identity repo — create_user_and_link, find_user_id, link.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from mindforge.infrastructure.persistence.identity_repo import (
    PostgresIdentityRepository,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_create_user_and_link(session):
    repo = PostgresIdentityRepository(session)

    user_id = await repo.create_user_and_link(
        provider="discord",
        external_id="discord-user-1",
        display_name="Alice",
        email="alice@example.com",
        metadata={"avatar": "http://cdn.discord.com/avatar.png"},
    )

    assert isinstance(user_id, uuid.UUID)

    # Should be findable now
    found = await repo.find_user_id("discord", "discord-user-1")
    assert found == user_id


@pytest.mark.integration
async def test_find_user_id_not_found(session):
    repo = PostgresIdentityRepository(session)
    result = await repo.find_user_id("github", "nonexistent-id")
    assert result is None


@pytest.mark.integration
async def test_link_additional_provider(session):
    repo = PostgresIdentityRepository(session)

    user_id = await repo.create_user_and_link(
        provider="discord",
        external_id="discord-user-2",
        display_name="Bob",
    )

    # Link a second provider to the same user
    await repo.link(user_id, "github", "github-bob-42", email="bob@github.com")

    found = await repo.find_user_id("github", "github-bob-42")
    assert found == user_id


@pytest.mark.integration
async def test_link_idempotent(session):
    """Linking the same provider+external_id twice must not raise."""
    repo = PostgresIdentityRepository(session)

    user_id = await repo.create_user_and_link(
        provider="google",
        external_id="google-user-3",
        display_name="Carol",
    )

    # Second link of the same identity should silently succeed (ON CONFLICT DO NOTHING)
    await repo.link(user_id, "google", "google-user-3")
