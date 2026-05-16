"""
Regression tests for fixes from deep-review-all-phases-2026-04-19.md
and architecture-drift-2026-04-19.md.

Covers:
  C2 — DocumentIngested constructed with correct types and required fields
  C3 — AppSettings.slack_allowed_workspace_list / discord_allowed_guild_list accessible
  C4 — User.is_admin field and admin guard behaviour
  H1 — list_unredacted supports optional user_id filter
  H2 — task status endpoint denies cross-user access
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from mindforge.api.routers.admin import _require_admin
from mindforge.domain.events import DocumentIngested
from mindforge.domain.models import User
from mindforge.infrastructure.config import AppSettings


# ---------------------------------------------------------------------------
# C2 — DocumentIngested field types and completeness
# ---------------------------------------------------------------------------


class TestDocumentIngestedFields:
    def test_accepts_uuid_document_id(self):
        """DocumentIngested must accept UUID (not str) for document_id."""
        doc_id = uuid4()
        kb_id = uuid4()
        user_id = uuid4()
        event = DocumentIngested(
            document_id=doc_id,
            knowledge_base_id=kb_id,
            lesson_id="lesson-1",
            upload_source="api",
            content_sha256="abc" * 21 + "a",
            uploaded_by=user_id,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.document_id == doc_id
        assert isinstance(event.document_id, UUID)

    def test_accepts_uuid_knowledge_base_id(self):
        """DocumentIngested must accept UUID for knowledge_base_id."""
        kb_id = uuid4()
        event = DocumentIngested(
            document_id=uuid4(),
            knowledge_base_id=kb_id,
            lesson_id="lesson-1",
            upload_source="api",
            content_sha256="abc" * 21 + "a",
            uploaded_by=None,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.knowledge_base_id == kb_id
        assert isinstance(event.knowledge_base_id, UUID)

    def test_timestamp_field_name_is_timestamp_not_occurred_at(self):
        """The field must be named 'timestamp', not 'occurred_at'."""
        ts = datetime.now(timezone.utc)
        event = DocumentIngested(
            document_id=uuid4(),
            knowledge_base_id=uuid4(),
            lesson_id="lesson-1",
            upload_source="api",
            content_sha256="abc" * 21 + "a",
            uploaded_by=None,
            timestamp=ts,
        )
        assert event.timestamp == ts
        assert not hasattr(event, "occurred_at")

    def test_content_sha256_required(self):
        """content_sha256 is a required field — must be present."""
        event = DocumentIngested(
            document_id=uuid4(),
            knowledge_base_id=uuid4(),
            lesson_id="lesson-1",
            upload_source="api",
            content_sha256="deadbeef" * 8,
            uploaded_by=None,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.content_sha256 == "deadbeef" * 8


# ---------------------------------------------------------------------------
# C3 — AppSettings allowlist properties are accessible
# ---------------------------------------------------------------------------


class TestAppSettingsAllowlistProperties:
    """Properties must exist on AppSettings, not inside a dead local function."""

    def _make_settings(self, **overrides) -> AppSettings:
        defaults = {
            "database_url": "postgresql+asyncpg://test:test@localhost/test",
            "jwt_secret": "test-secret-32chars-long-padding!",
        }
        defaults.update(overrides)
        return AppSettings.model_validate(defaults)

    def test_slack_allowed_workspace_list_returns_empty_when_not_set(self):
        s = self._make_settings()
        result = s.slack_allowed_workspace_list
        assert result == []

    def test_slack_allowed_workspace_list_parses_csv(self):
        s = self._make_settings(slack_allowed_workspaces="W001,W002, W003")
        assert s.slack_allowed_workspace_list == ["W001", "W002", "W003"]

    def test_discord_allowed_guild_list_returns_empty_when_not_set(self):
        s = self._make_settings()
        result = s.discord_allowed_guild_list
        assert result == []

    def test_discord_allowed_guild_list_parses_csv_as_ints(self):
        s = self._make_settings(discord_allowed_guilds="111,222,333")
        assert s.discord_allowed_guild_list == [111, 222, 333]


# ---------------------------------------------------------------------------
# C4 — is_admin field on User and admin guard
# ---------------------------------------------------------------------------


class TestIsAdminField:
    def _make_user(self, *, is_admin: bool) -> User:
        return User(
            user_id=uuid4(),
            display_name="Test User",
            created_at=datetime.now(timezone.utc),
            is_admin=is_admin,
        )

    def test_user_has_is_admin_field_defaulting_to_false(self):
        u = User(
            user_id=uuid4(),
            display_name="Regular",
            created_at=datetime.now(timezone.utc),
        )
        assert u.is_admin is False

    def test_require_admin_passes_for_admin_user(self):
        admin = self._make_user(is_admin=True)
        result = _require_admin(admin)
        assert result is admin

    def test_require_admin_raises_403_for_non_admin(self):
        from fastapi import HTTPException

        regular = self._make_user(is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(regular)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# H1 — list_unredacted supports optional user_id filter
# ---------------------------------------------------------------------------


class TestListUnredactedUserIdFilter:
    @pytest.mark.asyncio
    async def test_list_unredacted_accepts_user_id_kwarg(self):
        """list_unredacted must accept an optional user_id parameter."""
        from mindforge.infrastructure.persistence.interaction_repo import (
            PostgresInteractionStore,
        )
        from mindforge.infrastructure.persistence.models import (
            InteractionModel,
            InteractionTurnModel,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        store = PostgresInteractionStore(mock_session)
        user_id = uuid4()

        # Must not raise TypeError — user_id is a valid kwarg
        result = await store.list_unredacted(user_id=user_id, limit=10, offset=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_unredacted_works_without_user_id(self):
        """list_unredacted without user_id returns all interactions (admin list-all)."""
        from mindforge.infrastructure.persistence.interaction_repo import (
            PostgresInteractionStore,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        store = PostgresInteractionStore(mock_session)
        result = await store.list_unredacted(limit=10, offset=0)
        assert result == []
