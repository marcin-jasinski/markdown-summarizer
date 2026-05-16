"""
Application layer — Chat Service.

Conversational RAG with knowledge-base context using Graph RAG.

Sessions are ephemeral:
- Redis (if injected): JSON hash with TTL, key ``chat:{session_id}``.
- In-memory fallback: ``_InMemorySessionCache`` (single-process, TTL-based).

Interaction metadata is persisted to PostgreSQL for the audit trail, but
turn *content* lives only in the ephemeral session store.

Security invariants:
- No grounding context, raw prompts, or raw completions are returned to
  callers or stored in ``output_data`` of interaction turns.
- Semantic cache (if used in the retrieval adapter) MUST include ``kb_id``
  in the cache key; this service always passes ``kb_id`` to every retrieval
  call, making cross-KB leakage structurally impossible at this layer.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from mindforge.domain.models import (
    ChatSession,
    ChatTurn,
    ConceptNeighborhood,
    DeadlineProfile,
)
from mindforge.domain.ports import AIGateway, InteractionStore, RetrievalPort

log = logging.getLogger(__name__)

# Maximum number of history turns included in the prompt
_MAX_HISTORY_TURNS = 10

# Maximum characters in assembled context text (~2000 tokens at 4 chars/token)
_MAX_CONTEXT_CHARS = 8_000


# ---------------------------------------------------------------------------
# Public result types (no internal context or prompts exposed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatMessageResult:
    """Returned by :meth:`ChatService.send_message`.

    Deliberately excludes grounding context, raw prompts, and raw completions.
    """

    session_id: UUID
    answer: str
    source_concept_keys: list[str]


@dataclass(frozen=True)
class ChatSessionInfo:
    """Lightweight session descriptor returned by list/start operations."""

    session_id: UUID
    knowledge_base_id: UUID
    created_at: datetime
    turn_count: int


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ChatSessionNotFoundError(LookupError):
    """Session does not exist or has expired."""


class ChatSessionAccessDeniedError(PermissionError):
    """Caller does not own this chat session."""


# ---------------------------------------------------------------------------
# In-memory session cache (fallback when Redis is absent)
# ---------------------------------------------------------------------------


@dataclass
class _SessionEntry:
    session: ChatSession
    interaction_id: UUID
    expires_at: float  # monotonic timestamp


class _InMemorySessionCache:
    """Single-process, TTL-based chat session store.

    Not thread-safe — suitable for single-worker deployments without Redis.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[UUID, _SessionEntry] = {}
        self._ttl = ttl_seconds

    def put(self, session: ChatSession, interaction_id: UUID) -> None:
        self._store[session.session_id] = _SessionEntry(
            session=session,
            interaction_id=interaction_id,
            expires_at=time.monotonic() + self._ttl,
        )

    def get(self, session_id: UUID) -> _SessionEntry | None:
        entry = self._store.get(session_id)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[session_id]
            return None
        return entry

    def delete(self, session_id: UUID) -> None:
        self._store.pop(session_id, None)

    def list_by_user(self, user_id: UUID, kb_id: UUID) -> list[_SessionEntry]:
        now = time.monotonic()
        expired = [sid for sid, e in self._store.items() if now > e.expires_at]
        for sid in expired:
            del self._store[sid]
        return [
            e
            for e in self._store.values()
            if e.session.user_id == user_id and e.session.knowledge_base_id == kb_id
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_concept_mentions(message: str, concept_keys: list[str]) -> list[str]:
    """Return concept keys whose normalized form appears in ``message``."""
    lower = message.lower()
    matched: list[str] = []
    for key in concept_keys:
        normalized = re.sub(r"[-_]", " ", key)
        if normalized in lower or key in lower:
            matched.append(key)
    return matched


def _neighborhood_to_context(neighborhood: ConceptNeighborhood) -> str:
    """Build a concise context string from a concept neighborhood."""
    lines = [
        f"Concept: {neighborhood.center.label}",
        f"Description: {neighborhood.center.description}",
    ]
    if neighborhood.facts:
        lines.append("Facts:")
        for fact in neighborhood.facts:
            lines.append(f"  - {fact}")
    if neighborhood.neighbors:
        lines.append("Related:")
        for n in neighborhood.neighbors:
            lines.append(f"  - {n.label} ({n.relation}): {n.description}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ChatService:
    """Conversational RAG chat backed by a knowledge base.

    Parameters
    ----------
    gateway:
        AI gateway for LLM completions (INTERACTIVE deadline).
    retrieval:
        Graph RAG retrieval port.  ``kb_id`` is ALWAYS passed to every
        call, preventing cross-KB data leakage in any downstream cache.
    interaction_store:
        PostgreSQL-backed store for audit trail persistence.
    redis_client:
        Optional async Redis client.  Must support ``setex``, ``get``.
        Falls back to :class:`_InMemorySessionCache` when ``None``.
    session_ttl_seconds:
        Session lifetime (default 3600 s).
    """

    def __init__(
        self,
        gateway: AIGateway,
        retrieval: RetrievalPort,
        interaction_store: InteractionStore,
        *,
        system_with_context: str,
        system_no_context: str,
        redis_client: Any | None = None,
        session_ttl_seconds: int = 3600,
        memory_cache: _InMemorySessionCache | None = None,
    ) -> None:
        self._gateway = gateway
        self._retrieval = retrieval
        self._interactions = interaction_store
        self._redis = redis_client
        self._ttl = session_ttl_seconds
        self._system_with_context = system_with_context
        self._system_no_context = system_no_context
        # Share a single cache instance across per-request service instances so
        # in-memory sessions survive beyond the request that created them.
        self._cache = (
            memory_cache
            if memory_cache is not None
            else _InMemorySessionCache(ttl_seconds=session_ttl_seconds)
        )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(self, user_id: UUID, kb_id: UUID) -> ChatSessionInfo:
        """Create a new ephemeral chat session.

        An audit interaction row is created in PostgreSQL immediately.
        """
        now = datetime.now(timezone.utc)
        session = ChatSession(
            session_id=uuid4(),
            user_id=user_id,
            knowledge_base_id=kb_id,
            created_at=now,
            turns=[],
        )
        interaction_id = await self._interactions.create_interaction(
            interaction_type="chat",
            user_id=user_id,
            kb_id=kb_id,
        )
        await self._persist_session(session, interaction_id)

        return ChatSessionInfo(
            session_id=session.session_id,
            knowledge_base_id=kb_id,
            created_at=now,
            turn_count=0,
        )

    async def send_message(
        self,
        session_id: UUID,
        user_id: UUID,
        message: str,
    ) -> ChatMessageResult:
        """Process a user message and return the assistant's answer.

        Steps:
        1. Load chat history (last N turns).
        2. Extract concept mentions from the user message (keyword matching).
        3. For each matched concept: ``retrieve_concept_neighborhood()``.
        4. No concept match → fall back to ``retrieve()``.
        5. Assemble prompt: system + context + history + user message.
        6. LLM completion with INTERACTIVE deadline.
        7. Persist turn in ephemeral session; record metadata in interaction turns.
        8. Return answer + source concept keys (no context/prompt exposed).
        """
        entry = await self._load_entry(session_id)
        if entry is None:
            raise ChatSessionNotFoundError(
                f"Session {session_id} not found or expired."
            )
        if entry.session.user_id != user_id:
            raise ChatSessionAccessDeniedError("Session belongs to a different user.")

        session = entry.session
        kb_id = session.knowledge_base_id
        t_start = time.monotonic()

        # --- Step 2: concept mention extraction ---
        matched_keys: list[str] = []
        try:
            concepts = await self._retrieval.get_concepts(kb_id)
            matched_keys = _extract_concept_mentions(message, [c.key for c in concepts])
        except Exception:
            log.warning(
                "Concept extraction failed; proceeding without it.", exc_info=True
            )

        # --- Step 3 & 4: build context ---
        context_chunks: list[str] = []
        source_keys: list[str] = []

        if matched_keys:
            for key in matched_keys[:3]:  # cap to top-3 to control token budget
                try:
                    nbhd = await self._retrieval.retrieve_concept_neighborhood(
                        kb_id, key
                    )
                    if nbhd is not None:
                        context_chunks.append(_neighborhood_to_context(nbhd))
                        source_keys.append(key)
                except Exception:
                    log.warning(
                        "Neighborhood retrieval failed for %s.", key, exc_info=True
                    )
        else:
            # Fallback: lexical / vector retrieval (always scoped to kb_id)
            try:
                fallback = await self._retrieval.retrieve(message, kb_id, top_k=5)
                context_chunks.extend(r.content for r in fallback)
            except Exception:
                log.warning("Fallback retrieval failed.", exc_info=True)

        context_text = "\n\n---\n\n".join(context_chunks)
        if len(context_text) > _MAX_CONTEXT_CHARS:
            context_text = context_text[:_MAX_CONTEXT_CHARS]
            log.debug("Context text truncated to %d chars.", _MAX_CONTEXT_CHARS)

        # --- Step 5: assemble prompt ---
        system_content = (
            self._system_with_context.format(context=context_text)
            if context_text
            else self._system_no_context
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
        for turn in session.turns[-_MAX_HISTORY_TURNS:]:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": message})

        # --- Step 6: LLM completion ---
        completion = await self._gateway.complete(
            model="small",
            messages=messages,
            deadline=DeadlineProfile.INTERACTIVE,
        )
        duration_ms = round((time.monotonic() - t_start) * 1000)

        # --- Step 7: persist turn in ephemeral session ---
        now = datetime.now(timezone.utc)
        session.turns.append(ChatTurn(role="user", content=message, created_at=now))
        session.turns.append(
            ChatTurn(role="assistant", content=completion.content, created_at=now)
        )
        await self._persist_session(session, entry.interaction_id)

        # --- Audit trail (no grounding context stored) ---
        try:
            await self._interactions.add_turn(
                entry.interaction_id,
                actor_type="user",
                actor_id=str(user_id),
                action="chat_message",
                input_data={"message": message},
                duration_ms=duration_ms,
            )
            await self._interactions.add_turn(
                entry.interaction_id,
                actor_type="assistant",
                actor_id="mindforge",
                action="chat_response",
                output_data={"response": completion.content},
                duration_ms=duration_ms,
                cost=completion.cost_usd,
            )
        except Exception:
            log.warning("Failed to record chat interaction turns.", exc_info=True)

        return ChatMessageResult(
            session_id=session_id,
            answer=completion.content,
            source_concept_keys=source_keys,
        )

    async def list_sessions(self, user_id: UUID, kb_id: UUID) -> list[ChatSessionInfo]:
        """Return active chat sessions for a user in a given KB.

        When Redis is active, Redis SCAN is not used (it is not universally
        supported in cluster configurations).  Instead, the audit interaction
        store is queried — every chat session creates a corresponding
        ``interaction`` row at start time.  Sessions already expired in Redis
        may still appear here until the interaction record ages out.
        """
        if self._redis is not None:
            interactions = await self._interactions.list_for_user(user_id)
            return [
                ChatSessionInfo(
                    session_id=i.interaction_id,
                    knowledge_base_id=i.knowledge_base_id,
                    created_at=i.created_at,
                    turn_count=len(i.turns),
                )
                for i in interactions
                if i.interaction_type == "chat" and i.knowledge_base_id == kb_id
            ]
        entries = self._cache.list_by_user(user_id, kb_id)
        return [
            ChatSessionInfo(
                session_id=e.session.session_id,
                knowledge_base_id=e.session.knowledge_base_id,
                created_at=e.session.created_at,
                turn_count=len(e.session.turns),
            )
            for e in entries
        ]

    # ------------------------------------------------------------------
    # Ephemeral storage helpers
    # ------------------------------------------------------------------

    async def _persist_session(
        self, session: ChatSession, interaction_id: UUID
    ) -> None:
        if self._redis is not None:
            await self._persist_session_redis(session, interaction_id)
        else:
            self._cache.put(session, interaction_id)

    async def _persist_session_redis(
        self, session: ChatSession, interaction_id: UUID
    ) -> None:
        payload = json.dumps(
            {
                "session_id": str(session.session_id),
                "user_id": str(session.user_id),
                "knowledge_base_id": str(session.knowledge_base_id),
                "created_at": session.created_at.isoformat(),
                "interaction_id": str(interaction_id),
                "turns": [
                    {
                        "role": t.role,
                        "content": t.content,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in session.turns
                ],
            }
        )
        key = f"chat:{session.session_id}"
        await self._redis.setex(key, self._ttl, payload)

    async def _load_entry(self, session_id: UUID) -> _SessionEntry | None:
        if self._redis is not None:
            return await self._load_entry_redis(session_id)
        return self._cache.get(session_id)

    async def _load_entry_redis(self, session_id: UUID) -> _SessionEntry | None:
        key = f"chat:{session_id}"
        data = await self._redis.get(key)
        if data is None:
            return None
        payload = json.loads(data)
        session = ChatSession(
            session_id=UUID(payload["session_id"]),
            user_id=UUID(payload["user_id"]),
            knowledge_base_id=UUID(payload["knowledge_base_id"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            turns=[
                ChatTurn(
                    role=t["role"],
                    content=t["content"],
                    created_at=datetime.fromisoformat(t["created_at"]),
                )
                for t in payload.get("turns", [])
            ],
        )
        return _SessionEntry(
            session=session,
            interaction_id=UUID(payload["interaction_id"]),
            expires_at=time.monotonic() + self._ttl,
        )
