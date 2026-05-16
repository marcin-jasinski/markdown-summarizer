"""
Application layer — Knowledge Base Service.

Thin orchestration layer for knowledge-base CRUD, scoped to the owning user.
Delegates entirely to the :class:`~mindforge.domain.ports.KnowledgeBaseRepository`
port — no infrastructure imports.
"""

from __future__ import annotations

import logging
from uuid import UUID

from mindforge.domain.models import KnowledgeBase
from mindforge.domain.ports import KnowledgeBaseRepository

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class KnowledgeBaseNotFoundError(LookupError):
    """Knowledge base not found or does not belong to the requesting user."""


class KnowledgeBaseAlreadyExistsError(ValueError):
    """A knowledge base with the given name already exists for this user."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class KnowledgeBaseService:
    """CRUD operations for knowledge bases, scoped to the owning user.

    Parameters
    ----------
    kb_repo:
        Knowledge-base repository (fulfils
        :class:`~mindforge.domain.ports.KnowledgeBaseRepository`).
    """

    def __init__(self, kb_repo: KnowledgeBaseRepository) -> None:
        self._repo = kb_repo

    async def create(
        self,
        owner_id: UUID,
        name: str,
        description: str,
    ) -> KnowledgeBase:
        """Create and return a new knowledge base owned by ``owner_id``."""
        return await self._repo.create(
            owner_id=owner_id,
            name=name,
            description=description,
        )

    async def get(self, kb_id: UUID, owner_id: UUID) -> KnowledgeBase:
        """Return the KB or raise :class:`KnowledgeBaseNotFoundError`."""
        kb = await self._repo.get_by_id(kb_id, owner_id=owner_id)
        if kb is None:
            raise KnowledgeBaseNotFoundError(
                f"Knowledge base {kb_id} not found for user {owner_id}."
            )
        return kb

    async def list_for_user(self, owner_id: UUID) -> list[KnowledgeBase]:
        """Return all knowledge bases owned by ``owner_id``."""
        return await self._repo.list_by_owner(owner_id)

    async def update(
        self,
        kb_id: UUID,
        owner_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase:
        """Update KB fields; raise :class:`KnowledgeBaseNotFoundError` if absent."""
        kb = await self._repo.update(
            kb_id,
            owner_id=owner_id,
            name=name,
            description=description,
        )
        if kb is None:
            raise KnowledgeBaseNotFoundError(
                f"Knowledge base {kb_id} not found for user {owner_id}."
            )
        return kb

    async def delete(self, kb_id: UUID, owner_id: UUID) -> None:
        """Delete a KB; raise :class:`KnowledgeBaseNotFoundError` if absent."""
        deleted = await self._repo.delete(kb_id, owner_id=owner_id)
        if not deleted:
            raise KnowledgeBaseNotFoundError(
                f"Knowledge base {kb_id} not found for user {owner_id}."
            )
