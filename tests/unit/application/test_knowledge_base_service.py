"""
Unit tests for Phase 11 — Knowledge Base Service.

Covers:
  11.3.1  KnowledgeBaseService.create delegates to repository
  11.3.1  KnowledgeBaseService.get raises on missing KB
  11.3.1  KnowledgeBaseService.list_for_user returns repo results
  11.3.1  KnowledgeBaseService.update raises on missing KB
  11.3.1  KnowledgeBaseService.delete raises on missing KB
  11.3.1  User scoping: all operations pass owner_id to the repository
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mindforge.application.knowledge_base import (
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
)
from mindforge.domain.models import KnowledgeBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kb(owner_id=None) -> KnowledgeBase:
    return KnowledgeBase(
        kb_id=uuid4(),
        owner_id=owner_id or uuid4(),
        name="Test KB",
        description="A test knowledge base",
        created_at=datetime.now(timezone.utc),
        document_count=0,
    )


def _make_service(kb_repo=None) -> KnowledgeBaseService:
    return KnowledgeBaseService(kb_repo=kb_repo or AsyncMock())


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_delegates_to_repo(self):
        owner_id = uuid4()
        kb = _make_kb(owner_id)
        repo = AsyncMock()
        repo.create.return_value = kb

        service = _make_service(repo)
        result = await service.create(owner_id, "Test KB", "desc")

        repo.create.assert_awaited_once_with(
            owner_id=owner_id, name="Test KB", description="desc"
        )
        assert result == kb

    @pytest.mark.asyncio
    async def test_returns_knowledge_base(self):
        kb = _make_kb()
        repo = AsyncMock()
        repo.create.return_value = kb

        service = _make_service(repo)
        result = await service.create(uuid4(), "name", "desc")
        assert isinstance(result, KnowledgeBase)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_kb_when_found(self):
        owner_id = uuid4()
        kb = _make_kb(owner_id)
        repo = AsyncMock()
        repo.get_by_id.return_value = kb

        service = _make_service(repo)
        result = await service.get(kb.kb_id, owner_id)

        repo.get_by_id.assert_awaited_once_with(kb.kb_id, owner_id=owner_id)
        assert result == kb

    @pytest.mark.asyncio
    async def test_raises_not_found_when_absent(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        service = _make_service(repo)
        with pytest.raises(KnowledgeBaseNotFoundError):
            await service.get(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_passes_owner_id_to_repo(self):
        """User scoping: get() must always pass owner_id."""
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        owner_id = uuid4()

        service = _make_service(repo)
        try:
            await service.get(uuid4(), owner_id)
        except KnowledgeBaseNotFoundError:
            pass

        _, kwargs = repo.get_by_id.call_args
        assert kwargs.get("owner_id") == owner_id


# ---------------------------------------------------------------------------
# list_for_user
# ---------------------------------------------------------------------------


class TestListForUser:
    @pytest.mark.asyncio
    async def test_returns_repo_list(self):
        owner_id = uuid4()
        kbs = [_make_kb(owner_id), _make_kb(owner_id)]
        repo = AsyncMock()
        repo.list_by_owner.return_value = kbs

        service = _make_service(repo)
        result = await service.list_for_user(owner_id)

        repo.list_by_owner.assert_awaited_once_with(owner_id)
        assert result == kbs

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self):
        repo = AsyncMock()
        repo.list_by_owner.return_value = []

        service = _make_service(repo)
        result = await service.list_for_user(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    @pytest.mark.asyncio
    async def test_returns_updated_kb(self):
        owner_id = uuid4()
        kb = _make_kb(owner_id)
        repo = AsyncMock()
        repo.update.return_value = kb

        service = _make_service(repo)
        result = await service.update(kb.kb_id, owner_id, name="New Name")

        repo.update.assert_awaited_once_with(
            kb.kb_id, owner_id=owner_id, name="New Name", description=None
        )
        assert result == kb

    @pytest.mark.asyncio
    async def test_raises_not_found_when_repo_returns_none(self):
        repo = AsyncMock()
        repo.update.return_value = None

        service = _make_service(repo)
        with pytest.raises(KnowledgeBaseNotFoundError):
            await service.update(uuid4(), uuid4(), name="X")

    @pytest.mark.asyncio
    async def test_passes_owner_id_to_repo(self):
        """User scoping: update() must always pass owner_id."""
        repo = AsyncMock()
        repo.update.return_value = None
        owner_id = uuid4()

        service = _make_service(repo)
        try:
            await service.update(uuid4(), owner_id, name="x")
        except KnowledgeBaseNotFoundError:
            pass

        _, kwargs = repo.update.call_args
        assert kwargs.get("owner_id") == owner_id


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_calls_repo_delete(self):
        repo = AsyncMock()
        repo.delete.return_value = True
        owner_id = uuid4()
        kb_id = uuid4()

        service = _make_service(repo)
        await service.delete(kb_id, owner_id)

        repo.delete.assert_awaited_once_with(kb_id, owner_id=owner_id)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_repo_returns_false(self):
        repo = AsyncMock()
        repo.delete.return_value = False

        service = _make_service(repo)
        with pytest.raises(KnowledgeBaseNotFoundError):
            await service.delete(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_passes_owner_id_to_repo(self):
        """User scoping: delete() must always pass owner_id."""
        repo = AsyncMock()
        repo.delete.return_value = False
        owner_id = uuid4()

        service = _make_service(repo)
        try:
            await service.delete(uuid4(), owner_id)
        except KnowledgeBaseNotFoundError:
            pass

        _, kwargs = repo.delete.call_args
        assert kwargs.get("owner_id") == owner_id
