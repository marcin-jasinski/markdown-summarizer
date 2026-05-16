"""SSE events router — real-time processing updates via Server-Sent Events.

Falls back to polling ``outbox_events`` at 2s intervals when Redis is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mindforge.api.deps import get_current_user, get_kb_repo
from mindforge.domain.models import User
from mindforge.infrastructure.persistence.models import OutboxEventModel

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/events", tags=["events"])


async def _redis_event_stream(
    redis_client,
    kb_id: UUID,
) -> AsyncIterator[str]:
    """Subscribe to Redis Pub/Sub and yield SSE-formatted events."""
    channel = f"events:*"  # Subscribe to all event types
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=30.0
            )
            if message and message.get("type") == "pmessage":
                data = message.get("data", "")
                try:
                    payload = json.loads(data) if isinstance(data, str) else {}
                    # Filter by kb_id if present in payload
                    if str(kb_id) in json.dumps(payload):
                        yield f"data: {json.dumps(payload)}\n\n"
                except Exception:
                    pass
            else:
                # Keepalive comment
                yield ": keepalive\n\n"
            await asyncio.sleep(0.1)
    finally:
        await pubsub.punsubscribe(channel)
        await pubsub.aclose()


async def _polling_event_stream(
    engine,
    kb_id: UUID,
    user_id: UUID,
) -> AsyncIterator[str]:
    """Poll outbox_events table every 2s as Redis fallback."""
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    last_sequence: int = 0

    while True:
        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(OutboxEventModel)
                    .where(OutboxEventModel.sequence_num > last_sequence)
                    .order_by(OutboxEventModel.sequence_num)
                    .limit(50)
                )
                rows = result.scalars().all()
                for row in rows:
                    payload = row.payload or {}
                    if str(kb_id) in json.dumps(payload):
                        event_data = {
                            "event_type": row.event_type,
                            "payload": payload,
                            "created_at": row.created_at.isoformat(),
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                    last_sequence = max(last_sequence, row.sequence_num)
        except Exception as exc:
            log.warning("SSE polling error: %s", exc)

        yield ": keepalive\n\n"
        await asyncio.sleep(2.0)


@router.get("")
async def event_stream(
    kb_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    async with request.app.state.session_factory() as session:
        kb_repo = get_kb_repo(request, session)
        if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
            raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    redis_client = getattr(request.app.state, "redis_client", None)

    if redis_client is not None:
        stream = _redis_event_stream(redis_client, kb_id)
    else:
        stream = _polling_event_stream(
            request.app.state.db_engine, kb_id, current_user.user_id
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
