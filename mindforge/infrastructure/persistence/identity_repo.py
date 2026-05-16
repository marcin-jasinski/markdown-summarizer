"""
PostgreSQL implementation of `ExternalIdentityRepository`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import User
from mindforge.infrastructure.persistence.models import (
    ExternalIdentityModel,
    UserModel,
)


class PostgresIdentityRepository:
    """Fulfils the `ExternalIdentityRepository` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def find_user_id(self, provider: str, external_id: str) -> uuid.UUID | None:
        result = await self._session.execute(
            select(ExternalIdentityModel.user_id).where(
                ExternalIdentityModel.provider == provider,
                ExternalIdentityModel.external_id == external_id,
            )
        )
        row = result.scalar_one_or_none()
        return row if row is not None else None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def link(
        self,
        user_id: uuid.UUID,
        provider: str,
        external_id: str,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """INSERT an external identity link (idempotent via upsert)."""
        stmt = (
            pg_insert(ExternalIdentityModel)
            .values(
                user_id=user_id,
                provider=provider,
                external_id=external_id,
                email=email,
                metadata_=metadata or {},
            )
            .on_conflict_do_nothing(
                constraint="external_identities_provider_external_id_key"
            )
        )
        await self._session.execute(stmt)

    async def create_user_and_link(
        self,
        provider: str,
        external_id: str,
        display_name: str,
        email: str | None = None,
        avatar_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        """
        Atomically create a `users` row and an `external_identities` row.
        Returns the new user_id.
        """
        now = datetime.now(timezone.utc)
        user_row = UserModel(
            display_name=display_name,
            email=email,
            avatar_url=avatar_url,
            created_at=now,
            last_login_at=now,
        )
        self._session.add(user_row)
        await self._session.flush()  # obtain user_id

        identity_row = ExternalIdentityModel(
            user_id=user_row.user_id,
            provider=provider,
            external_id=external_id,
            email=email,
            metadata_=metadata or {},
        )
        self._session.add(identity_row)
        await self._session.flush()

        return user_row.user_id
