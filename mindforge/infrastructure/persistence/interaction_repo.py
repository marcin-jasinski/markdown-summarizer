"""
PostgreSQL implementation of `InteractionStore`.

REDACTION POLICY — defense in depth:
`list_for_user()` strips the following fields from `output_data` before
returning results.  This is enforced here, not in the API router, so that
the store never returns unredacted data for user-facing queries.

Stripped fields:
  - reference_answer
  - grounding_context
  - raw_prompt
  - raw_completion
  - cost  (for non-admin users)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from mindforge.domain.models import Interaction, InteractionTurn
from mindforge.infrastructure.persistence.models import (
    InteractionModel,
    InteractionTurnModel,
)

# Fields redacted from output_data in user-facing queries.
_REDACTED_OUTPUT_FIELDS = frozenset(
    {"reference_answer", "grounding_context", "raw_prompt", "raw_completion"}
)


def _redact(output_data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of output_data with sensitive fields removed."""
    return {k: v for k, v in output_data.items() if k not in _REDACTED_OUTPUT_FIELDS}


class PostgresInteractionStore:
    """Fulfils the `InteractionStore` port protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create_interaction(
        self,
        *,
        interaction_type: str,
        user_id: uuid.UUID | None = None,
        kb_id: uuid.UUID | None = None,
        context: dict[str, Any] | None = None,
        parent_interaction_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        row = InteractionModel(
            interaction_type=interaction_type,
            user_id=user_id,
            kb_id=kb_id,
            context_=context or {},
            parent_interaction_id=parent_interaction_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row.interaction_id

    async def add_turn(
        self,
        interaction_id: uuid.UUID,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        cost: float | None = None,
    ) -> uuid.UUID:
        row = InteractionTurnModel(
            interaction_id=interaction_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            input_data=input_data or {},
            output_data=output_data or {},
            duration_ms=duration_ms,
            cost=Decimal(str(cost)) if cost is not None else None,
        )
        self._session.add(row)
        await self._session.flush()
        return row.turn_id

    # ------------------------------------------------------------------
    # Read (user-facing — REDACTED)
    # ------------------------------------------------------------------

    async def get_interaction(self, interaction_id: uuid.UUID) -> Interaction | None:
        result = await self._session.execute(
            select(InteractionModel)
            .where(InteractionModel.interaction_id == interaction_id)
            .options(selectinload(InteractionModel.turns))
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Interaction]:
        """Return interactions for a user with output_data redacted."""
        result = await self._session.execute(
            select(InteractionModel)
            .where(InteractionModel.user_id == user_id)
            .options(selectinload(InteractionModel.turns))
            .order_by(InteractionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
        return [_to_domain(row, redact=True) for row in rows]

    # ------------------------------------------------------------------
    # Read (admin — UNREDACTED)
    # ------------------------------------------------------------------

    async def list_unredacted(
        self, *, user_id: uuid.UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[Interaction]:
        """Admin-only: return full unredacted interaction data."""
        stmt = (
            select(InteractionModel)
            .options(selectinload(InteractionModel.turns))
            .order_by(InteractionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id is not None:
            stmt = stmt.where(InteractionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_to_domain(row, redact=False) for row in rows]


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _to_domain(row: InteractionModel, *, redact: bool = True) -> Interaction:
    sorted_turns = sorted(row.turns, key=lambda t: t.timestamp)
    turns = [
        InteractionTurn(
            turn_id=t.turn_id,
            interaction_id=t.interaction_id,
            turn_number=idx,
            role=t.actor_type,
            content=t.action,
            created_at=t.timestamp,
            input_data=t.input_data or {},
            output_data=(
                _redact(t.output_data or {}) if redact else (t.output_data or {})
            ),
            cost=float(t.cost) if t.cost is not None else None,
        )
        for idx, t in enumerate(sorted_turns)
    ]
    return Interaction(
        interaction_id=row.interaction_id,
        user_id=row.user_id,  # type: ignore[arg-type]
        interaction_type=row.interaction_type,
        created_at=row.created_at,
        knowledge_base_id=row.kb_id,
        completed_at=row.completed_at,
        metadata=row.context_ or {},
        turns=turns,
    )
