"""
Unit tests for Phase 11 — Chat Service.

Covers:
  11.2.2  start_session creates ephemeral session and audit interaction
  11.2.3  send_message: concept extraction, retrieval, prompt assembly, response
  11.2.3  send_message: fallback to retrieve() when no concepts matched
  11.2.4  ChatSessionNotFoundError on missing/expired session
  11.2.4  ChatSessionAccessDeniedError on wrong user
  11.3    list_sessions returns in-memory sessions for user+KB
  11.4.5  Security invariant: kb_id always passed to retrieval calls
  11.4.5  No grounding context or prompts in ChatMessageResult
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from mindforge.application.chat import (
    ChatMessageResult,
    ChatService,
    ChatSessionAccessDeniedError,
    ChatSessionInfo,
    ChatSessionNotFoundError,
    _extract_concept_mentions,
    _neighborhood_to_context,
)
from mindforge.domain.models import (
    CompletionResult,
    ConceptNeighborhood,
    ConceptNode,
    RelatedConceptSummary,
    RetrievalResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completion(content: str = "AI answer") -> CompletionResult:
    return CompletionResult(
        content=content,
        input_tokens=10,
        output_tokens=20,
        model="gpt-4o-mini",
        provider="openai",
        latency_ms=100.0,
        cost_usd=0.001,
    )


def _make_neighborhood(key: str = "python-oop") -> ConceptNeighborhood:
    return ConceptNeighborhood(
        center=ConceptNode(key=key, label="Python OOP", description="OOP in Python"),
        neighbors=[
            RelatedConceptSummary(
                key="inheritance",
                label="Inheritance",
                relation="EXTENDS",
                description="Class hierarchy",
            )
        ],
        depth=2,
        facts=["Classes define objects", "Methods are class functions"],
    )


def _make_service(
    *,
    gateway=None,
    retrieval=None,
    interaction_store=None,
    redis_client=None,
    session_ttl_seconds: int = 3600,
) -> ChatService:
    return ChatService(
        gateway=gateway or AsyncMock(),
        retrieval=retrieval or AsyncMock(),
        interaction_store=interaction_store or AsyncMock(),
        redis_client=redis_client,
        session_ttl_seconds=session_ttl_seconds,
        system_with_context="Context: {context}",
        system_no_context="No context available.",
    )


# ---------------------------------------------------------------------------
# _extract_concept_mentions helper
# ---------------------------------------------------------------------------


class TestExtractConceptMentions:
    def test_matches_by_normalized_key(self):
        result = _extract_concept_mentions(
            "Tell me about python oop concepts", ["python-oop", "inheritance"]
        )
        assert "python-oop" in result

    def test_matches_by_raw_key_substring(self):
        result = _extract_concept_mentions("explain inheritance", ["inheritance"])
        assert "inheritance" in result

    def test_no_match_returns_empty(self):
        result = _extract_concept_mentions("hello world", ["python-oop"])
        assert result == []

    def test_case_insensitive_match(self):
        result = _extract_concept_mentions("What is Inheritance?", ["inheritance"])
        assert "inheritance" in result


# ---------------------------------------------------------------------------
# _neighborhood_to_context helper
# ---------------------------------------------------------------------------


class TestNeighborhoodToContext:
    def test_includes_center_label_and_description(self):
        nbhd = _make_neighborhood()
        ctx = _neighborhood_to_context(nbhd)
        assert "Python OOP" in ctx
        assert "OOP in Python" in ctx

    def test_includes_facts(self):
        nbhd = _make_neighborhood()
        ctx = _neighborhood_to_context(nbhd)
        assert "Classes define objects" in ctx

    def test_includes_related_concepts(self):
        nbhd = _make_neighborhood()
        ctx = _neighborhood_to_context(nbhd)
        assert "Inheritance" in ctx


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


class TestStartSession:
    @pytest.mark.asyncio
    async def test_creates_interaction_in_store(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(interaction_store=interaction_store)
        user_id = uuid4()
        kb_id = uuid4()

        info = await service.start_session(user_id, kb_id)

        interaction_store.create_interaction.assert_awaited_once_with(
            interaction_type="chat",
            user_id=user_id,
            kb_id=kb_id,
        )
        assert isinstance(info, ChatSessionInfo)
        assert info.knowledge_base_id == kb_id
        assert info.turn_count == 0

    @pytest.mark.asyncio
    async def test_session_stored_in_memory_cache(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(interaction_store=interaction_store)
        user_id = uuid4()
        kb_id = uuid4()

        info = await service.start_session(user_id, kb_id)

        entry = service._cache.get(info.session_id)
        assert entry is not None
        assert entry.session.user_id == user_id


# ---------------------------------------------------------------------------
# send_message — session validation
# ---------------------------------------------------------------------------


class TestSendMessageSessionValidation:
    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_session(self):
        service = _make_service()

        with pytest.raises(ChatSessionNotFoundError):
            await service.send_message(uuid4(), uuid4(), "hello")

    @pytest.mark.asyncio
    async def test_raises_access_denied_for_wrong_user(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()
        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion()

        service = _make_service(interaction_store=interaction_store, gateway=gateway)
        owner_id = uuid4()
        kb_id = uuid4()

        info = await service.start_session(owner_id, kb_id)

        with pytest.raises(ChatSessionAccessDeniedError):
            await service.send_message(info.session_id, uuid4(), "hi")


# ---------------------------------------------------------------------------
# send_message — concept extraction & retrieval
# ---------------------------------------------------------------------------


class TestSendMessageRetrieval:
    @pytest.mark.asyncio
    async def test_calls_get_concepts_then_neighborhood(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        from mindforge.domain.models import ConceptNode

        retrieval.get_concepts.return_value = [
            ConceptNode(key="python-oop", label="Python OOP", description="")
        ]
        nbhd = _make_neighborhood("python-oop")
        retrieval.retrieve_concept_neighborhood.return_value = nbhd

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion("answer about OOP")

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        kb_id = uuid4()
        info = await service.start_session(user_id, kb_id)

        result = await service.send_message(
            info.session_id, user_id, "tell me about python oop"
        )

        retrieval.get_concepts.assert_awaited_once_with(kb_id)
        retrieval.retrieve_concept_neighborhood.assert_awaited_once_with(
            kb_id, "python-oop"
        )
        assert "python-oop" in result.source_concept_keys

    @pytest.mark.asyncio
    async def test_falls_back_to_retrieve_when_no_concepts_matched(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []  # no concepts in KB
        retrieval.retrieve.return_value = [
            RetrievalResult(
                content="some fallback content",
                source_lesson_id="lesson-x",
                source_document_id=uuid4(),
                score=0.5,
            )
        ]

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion("fallback answer")

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        kb_id = uuid4()
        info = await service.start_session(user_id, kb_id)

        result = await service.send_message(info.session_id, user_id, "obscure query")

        retrieval.retrieve.assert_awaited_once()
        # kb_id MUST be passed to retrieval — security invariant
        call_args = retrieval.retrieve.call_args
        assert call_args.args[1] == kb_id or call_args.kwargs.get("kb_id") == kb_id

    @pytest.mark.asyncio
    async def test_kb_id_always_passed_to_retrieval(self):
        """Security invariant: kb_id is always included in every retrieval call.

        This prevents cross-KB data leakage in any downstream semantic cache.
        """
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        from mindforge.domain.models import ConceptNode

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = [
            ConceptNode(key="some-concept", label="Some Concept", description="")
        ]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood(
            "some-concept"
        )

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion()

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        kb_id = uuid4()
        info = await service.start_session(user_id, kb_id)
        await service.send_message(
            info.session_id, user_id, "tell me about some concept"
        )

        # get_concepts must be called with kb_id
        retrieval.get_concepts.assert_awaited_once_with(kb_id)
        # neighborhood retrieval must be called with kb_id as first positional arg
        nbhd_call = retrieval.retrieve_concept_neighborhood.call_args
        assert nbhd_call.args[0] == kb_id


# ---------------------------------------------------------------------------
# send_message — response format
# ---------------------------------------------------------------------------


class TestSendMessageResponse:
    @pytest.mark.asyncio
    async def test_returns_chat_message_result(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []
        retrieval.retrieve.return_value = []

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion("the answer")

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        info = await service.start_session(user_id, uuid4())
        result = await service.send_message(info.session_id, user_id, "q")

        assert isinstance(result, ChatMessageResult)
        assert result.answer == "the answer"
        assert result.session_id == info.session_id

    @pytest.mark.asyncio
    async def test_turn_history_is_accumulated(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []
        retrieval.retrieve.return_value = []

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion()

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        info = await service.start_session(user_id, uuid4())

        await service.send_message(info.session_id, user_id, "first message")
        await service.send_message(info.session_id, user_id, "second message")

        entry = service._cache.get(info.session_id)
        assert len(entry.session.turns) == 4  # 2 user + 2 assistant


# ---------------------------------------------------------------------------
# Security invariant: no grounding context / prompts in result
# ---------------------------------------------------------------------------


class TestChatSecurityInvariant:
    @pytest.mark.asyncio
    async def test_result_contains_no_sensitive_fields(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []
        retrieval.retrieve.return_value = []

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion("safe answer")

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        info = await service.start_session(user_id, uuid4())
        result = await service.send_message(info.session_id, user_id, "q")

        assert not hasattr(result, "grounding_context")
        assert not hasattr(result, "reference_answer")
        assert not hasattr(result, "raw_prompt")
        assert not hasattr(result, "raw_completion")

    @pytest.mark.asyncio
    async def test_audit_turn_output_data_excludes_grounding(self):
        """Grounding context must NOT be stored in interaction output_data."""
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []
        retrieval.retrieve.return_value = [
            RetrievalResult(
                content="SECRET GROUNDING CONTEXT",
                source_lesson_id="lesson",
                source_document_id=uuid4(),
                score=0.9,
            )
        ]

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion("answer")

        service = _make_service(
            retrieval=retrieval,
            gateway=gateway,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        info = await service.start_session(user_id, uuid4())
        await service.send_message(info.session_id, user_id, "q")

        # Check all add_turn calls — none should include grounding context
        for call in interaction_store.add_turn.call_args_list:
            output_data = call.kwargs.get("output_data") or {}
            assert "grounding_context" not in output_data
            assert "SECRET GROUNDING CONTEXT" not in str(output_data)


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    @pytest.mark.asyncio
    async def test_returns_sessions_for_user_and_kb(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(interaction_store=interaction_store)
        user_id = uuid4()
        kb_id = uuid4()

        info1 = await service.start_session(user_id, kb_id)
        info2 = await service.start_session(user_id, kb_id)

        sessions = await service.list_sessions(user_id, kb_id)
        session_ids = {s.session_id for s in sessions}
        assert info1.session_id in session_ids
        assert info2.session_id in session_ids

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_sessions(self):
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        service = _make_service(interaction_store=interaction_store)
        kb_id = uuid4()
        user_a = uuid4()
        user_b = uuid4()

        await service.start_session(user_a, kb_id)
        await service.start_session(user_b, kb_id)

        sessions_a = await service.list_sessions(user_a, kb_id)
        assert all(s.knowledge_base_id == kb_id for s in sessions_a)
        # user_b's session should NOT appear
        entry_b_ids = {s.session_id for s in sessions_a}
        sessions_b = await service.list_sessions(user_b, kb_id)
        assert not any(s.session_id in entry_b_ids for s in sessions_b)


# ---------------------------------------------------------------------------
# History sliding window (_MAX_HISTORY_TURNS)
# ---------------------------------------------------------------------------


class TestHistorySlidingWindow:
    @pytest.mark.asyncio
    async def test_history_is_bounded_at_max_turns(self):
        """After N sends the prompt must contain at most _MAX_HISTORY_TURNS history turns."""
        from mindforge.application.chat import _MAX_HISTORY_TURNS

        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        retrieval = AsyncMock()
        retrieval.get_concepts.return_value = []
        retrieval.retrieve.return_value = []

        gateway = AsyncMock()
        gateway.complete.return_value = _make_completion()

        service = _make_service(
            gateway=gateway,
            retrieval=retrieval,
            interaction_store=interaction_store,
        )
        user_id = uuid4()
        info = await service.start_session(user_id, uuid4())

        # Send _MAX_HISTORY_TURNS + 2 messages to force the window to kick in
        for _ in range(_MAX_HISTORY_TURNS + 2):
            await service.send_message(info.session_id, user_id, "question")

        # Inspect the messages list passed on the *last* gateway call
        last_messages = gateway.complete.call_args.kwargs["messages"]
        # Strip the system prompt (first element) and the current user message (last)
        history_messages = last_messages[1:-1]
        assert len(history_messages) <= _MAX_HISTORY_TURNS


# ---------------------------------------------------------------------------
# list_sessions — Redis fallback path
# ---------------------------------------------------------------------------


class TestListSessionsRedisFallback:
    @pytest.mark.asyncio
    async def test_redis_path_uses_interaction_store(self):
        """With Redis active, list_sessions must query the interaction store."""
        from mindforge.domain.models import Interaction
        from datetime import datetime, timezone

        kb_id = uuid4()
        user_id = uuid4()
        interaction_id = uuid4()
        mock_interaction = Interaction(
            interaction_id=interaction_id,
            user_id=user_id,
            interaction_type="chat",
            created_at=datetime.now(timezone.utc),
            knowledge_base_id=kb_id,
            turns=[],
        )
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = interaction_id
        interaction_store.list_for_user.return_value = [mock_interaction]

        redis_client = AsyncMock()  # non-None → triggers Redis code path
        service = _make_service(
            interaction_store=interaction_store,
            redis_client=redis_client,
        )

        sessions = await service.list_sessions(user_id, kb_id)

        interaction_store.list_for_user.assert_awaited_once_with(user_id)
        assert len(sessions) == 1
        assert sessions[0].session_id == interaction_id
        assert sessions[0].knowledge_base_id == kb_id

    @pytest.mark.asyncio
    async def test_redis_path_filters_by_kb_id(self):
        """Only chat interactions for the requested kb_id are returned."""
        from mindforge.domain.models import Interaction
        from datetime import datetime, timezone

        user_id = uuid4()
        kb_a = uuid4()
        kb_b = uuid4()

        def _make_interaction(kb_id):
            return Interaction(
                interaction_id=uuid4(),
                user_id=user_id,
                interaction_type="chat",
                created_at=datetime.now(timezone.utc),
                knowledge_base_id=kb_id,
                turns=[],
            )

        interaction_store = AsyncMock()
        interaction_store.list_for_user.return_value = [
            _make_interaction(kb_a),
            _make_interaction(kb_b),
        ]

        service = _make_service(
            interaction_store=interaction_store,
            redis_client=AsyncMock(),
        )

        sessions = await service.list_sessions(user_id, kb_a)

        assert len(sessions) == 1
        assert sessions[0].knowledge_base_id == kb_a

    @pytest.mark.asyncio
    async def test_redis_path_excludes_non_chat_interactions(self):
        """Non-chat interaction types must be filtered out."""
        from mindforge.domain.models import Interaction
        from datetime import datetime, timezone

        user_id = uuid4()
        kb_id = uuid4()

        chat_ix = Interaction(
            interaction_id=uuid4(),
            user_id=user_id,
            interaction_type="chat",
            created_at=datetime.now(timezone.utc),
            knowledge_base_id=kb_id,
            turns=[],
        )
        search_ix = Interaction(
            interaction_id=uuid4(),
            user_id=user_id,
            interaction_type="search",
            created_at=datetime.now(timezone.utc),
            knowledge_base_id=kb_id,
            turns=[],
        )

        interaction_store = AsyncMock()
        interaction_store.list_for_user.return_value = [chat_ix, search_ix]

        service = _make_service(
            interaction_store=interaction_store,
            redis_client=AsyncMock(),
        )

        sessions = await service.list_sessions(user_id, kb_id)

        assert len(sessions) == 1
        assert sessions[0].session_id == chat_ix.interaction_id
