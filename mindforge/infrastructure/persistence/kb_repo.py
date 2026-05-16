"""
PostgreSQL repository for KnowledgeBase management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import KnowledgeBase
from mindforge.infrastructure.persistence.models import (
    DocumentModel,
    KnowledgeBaseModel,
)


class PostgresKnowledgeBaseRepository:
    """CRUD operations for ``KnowledgeBase`` entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(
        self,
        owner_id: uuid.UUID,
        name: str,
        description: str,
        prompt_locale: str = "pl",
    ) -> KnowledgeBase:
        row = KnowledgeBaseModel(
            owner_id=owner_id,
            name=name,
            description=description,
            prompt_locale=prompt_locale,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_domain(row, document_count=0)

    async def update(
        self,
        kb_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        prompt_locale: str | None = None,
    ) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseModel).where(
                KnowledgeBaseModel.kb_id == kb_id,
                KnowledgeBaseModel.owner_id == owner_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if prompt_locale is not None:
            row.prompt_locale = prompt_locale
        await self._session.flush()
        count = await self._count_documents(kb_id)
        return self._to_domain(row, document_count=count)

    async def delete(self, kb_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(KnowledgeBaseModel).where(
                KnowledgeBaseModel.kb_id == kb_id,
                KnowledgeBaseModel.owner_id == owner_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        return True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(
        self, kb_id: uuid.UUID, owner_id: uuid.UUID | None = None
    ) -> KnowledgeBase | None:
        stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.kb_id == kb_id)
        if owner_id is not None:
            stmt = stmt.where(KnowledgeBaseModel.owner_id == owner_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        count = await self._count_documents(kb_id)
        return self._to_domain(row, document_count=count)

    async def list_by_owner(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[KnowledgeBase]:
        result = await self._session.execute(
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.owner_id == owner_id)
            .order_by(KnowledgeBaseModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
        out = []
        for row in rows:
            count = await self._count_documents(row.kb_id)
            out.append(self._to_domain(row, document_count=count))
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _count_documents(self, kb_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(DocumentModel)
            .where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one() or 0

    @staticmethod
    def _to_domain(row: KnowledgeBaseModel, document_count: int) -> KnowledgeBase:
        return KnowledgeBase(
            kb_id=row.kb_id,
            owner_id=row.owner_id,
            name=row.name,
            description=row.description,
            created_at=row.created_at,
            document_count=document_count,
            prompt_locale=row.prompt_locale,
        )
