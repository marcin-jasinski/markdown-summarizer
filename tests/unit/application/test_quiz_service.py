"""
Unit tests for Phase 10 — Quiz Service.

Covers:
  10.5.2  Quiz session lifecycle: start → answer → evaluation
  10.5.3  Reference answer is reused, not regenerated
  10.5.5  Quiz session TTL behaviour
  10.5.6  Security invariant: quiz responses NEVER contain reference_answer,
          grounding_context, raw_prompt, or raw_completion
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from mindforge.application.quiz import (
    NoWeakConceptsError,
    QuizAccessDeniedError,
    QuizEvalResult,
    QuizQuestionNotFoundError,
    QuizService,
    QuizSessionNotFoundError,
    QuizStartResult,
    _neighborhood_to_context,
)
from mindforge.domain.agents import AgentContext, AgentResult, ProcessingSettings
from mindforge.domain.models import (
    ConceptNeighborhood,
    ConceptNode,
    QuizQuestion,
    QuizSession,
    RelatedConceptSummary,
    ReviewResult,
    WeakConcept,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings() -> ProcessingSettings:
    return ProcessingSettings(
        model_tier_map={"large": "gpt-4o", "small": "gpt-4o-mini"}
    )


def _make_service(
    *,
    gateway=None,
    retrieval=None,
    quiz_sessions=None,
    study_progress=None,
    interaction_store=None,
    settings=None,
    event_publisher=None,
    quiz_generator=None,
    quiz_evaluator=None,
    quiz_ttl_seconds: int = 1800,
) -> QuizService:
    return QuizService(
        gateway=gateway or AsyncMock(),
        retrieval=retrieval or AsyncMock(),
        quiz_sessions=quiz_sessions or AsyncMock(),
        study_progress=study_progress or AsyncMock(),
        interaction_store=interaction_store or AsyncMock(),
        settings=settings or _make_settings(),
        event_publisher=event_publisher,
        quiz_generator=quiz_generator or AsyncMock(),
        quiz_evaluator=quiz_evaluator or AsyncMock(),
        quiz_ttl_seconds=quiz_ttl_seconds,
    )


def _make_weak_concept(
    key: str = "python-oop", label: str = "Python OOP"
) -> WeakConcept:
    return WeakConcept(key=key, label=label, due_count=3)


def _make_neighborhood(key: str = "python-oop") -> ConceptNeighborhood:
    return ConceptNeighborhood(
        center=ConceptNode(
            key=key,
            label="Python OOP",
            description="Object-oriented programming in Python",
        ),
        neighbors=[
            RelatedConceptSummary(
                key="inheritance",
                label="Inheritance",
                relation="EXTENDS",
                description="Class hierarchy",
            )
        ],
        depth=2,
        facts=["Classes define object structure", "Methods are functions on objects"],
    )


def _make_quiz_question(
    question_id: str = "test-qid",
    reference_answer: str = "secret answer",
    grounding_context: str = "secret context",
) -> QuizQuestion:
    return QuizQuestion(
        question_id=question_id,
        question_text="What is a class?",
        question_type="open_ended",
        reference_answer=reference_answer,
        grounding_context=grounding_context,
        lesson_id="python-oop",
    )


def _make_session(
    user_id: UUID,
    question_id: str = "test-qid",
    expires_at: datetime | None = None,
) -> QuizSession:
    session_id = uuid4()
    now = datetime.now(timezone.utc)
    return QuizSession(
        session_id=session_id,
        user_id=user_id,
        kb_id=uuid4(),
        questions=[_make_quiz_question(question_id=question_id)],
        created_at=now,
        expires_at=expires_at or (now + timedelta(seconds=1800)),
    )


# ---------------------------------------------------------------------------
# start_session tests
# ---------------------------------------------------------------------------


class TestStartSession:
    @pytest.mark.asyncio
    async def test_happy_path_returns_start_result(self):
        """Happy path: weak concept found, agent succeeds, result returned."""
        user_id = uuid4()
        kb_id = uuid4()

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood()

        quiz_sessions = AsyncMock()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        # Fake QuizGeneratorAgent that injects a question into metadata
        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            q = QuizQuestion(
                question_id="",
                question_text="What is a class?",
                question_type="open_ended",
                reference_answer="A class is a blueprint",
                grounding_context="Context about classes",
                lesson_id="python-oop",
            )
            ctx.metadata["quiz_question"] = q
            return AgentResult(success=True, output_key="quiz_question", tokens_used=10)

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=quiz_sessions,
            interaction_store=interaction_store,
            quiz_generator=mock_gen,
        )
        result = await service.start_session(user_id, kb_id)

        assert isinstance(result, QuizStartResult)
        assert result.session_id is not None
        assert result.question_id
        assert result.question_text == "What is a class?"
        assert result.question_type == "open_ended"
        assert result.lesson_id == "python-oop"

    @pytest.mark.asyncio
    async def test_result_has_no_sensitive_fields(self):
        """Security invariant: QuizStartResult must not expose reference_answer
        or grounding_context."""
        user_id = uuid4()
        kb_id = uuid4()

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open_ended",
                reference_answer="TOP SECRET",
                grounding_context="ALSO SECRET",
                lesson_id="x",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=AsyncMock(),
            interaction_store=interaction_store,
            quiz_generator=mock_gen,
        )
        result = await service.start_session(user_id, kb_id)

        result_dict = result.__dict__
        assert "reference_answer" not in result_dict
        assert "grounding_context" not in result_dict
        assert "TOP SECRET" not in str(result_dict)
        assert "ALSO SECRET" not in str(result_dict)

    @pytest.mark.asyncio
    async def test_raises_no_weak_concepts_when_empty(self):
        """NoWeakConceptsError raised when retrieval returns empty list."""
        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = []

        service = _make_service(retrieval=retrieval)
        with pytest.raises(NoWeakConceptsError):
            await service.start_session(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_agent_failure(self):
        """RuntimeError propagated when QuizGeneratorAgent returns failure."""
        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood()

        async def _fail(ctx: AgentContext) -> AgentResult:
            return AgentResult(
                success=False, output_key="quiz_question", error="LLM down"
            )

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fail)
        service = _make_service(
            retrieval=retrieval, quiz_sessions=AsyncMock(), quiz_generator=mock_gen
        )
        with pytest.raises(RuntimeError, match="LLM down"):
            await service.start_session(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_session_stored_server_side_with_reference_answer(self):
        """Session stored by QuizSessionStore contains the full question including
        reference_answer (server-side only — not returned to caller)."""
        user_id = uuid4()
        kb_id = uuid4()

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        stored_sessions: list[QuizSession] = []
        quiz_sessions = AsyncMock()
        quiz_sessions.create_session.side_effect = lambda s: stored_sessions.append(s)

        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open_ended",
                reference_answer="SECRET_REF",
                grounding_context="SECRET_CTX",
                lesson_id="x",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=quiz_sessions,
            interaction_store=interaction_store,
            quiz_generator=mock_gen,
        )
        await service.start_session(user_id, kb_id)

        assert stored_sessions, "Session should have been persisted"
        stored = stored_sessions[0]
        assert stored.questions[0].reference_answer == "SECRET_REF"
        assert stored.questions[0].grounding_context == "SECRET_CTX"

    @pytest.mark.asyncio
    async def test_session_ttl_set_correctly(self):
        """Session expires_at is set to now + quiz_ttl_seconds."""
        user_id = uuid4()
        kb_id = uuid4()
        ttl = 600

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = None
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        stored_sessions: list[QuizSession] = []
        quiz_sessions = AsyncMock()
        quiz_sessions.create_session.side_effect = lambda s: stored_sessions.append(s)

        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open",
                reference_answer="R",
                grounding_context="G",
                lesson_id="x",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=quiz_sessions,
            interaction_store=interaction_store,
            quiz_ttl_seconds=ttl,
            quiz_generator=mock_gen,
        )
        result = await service.start_session(user_id, kb_id)

        session = stored_sessions[0]
        delta = (session.expires_at - session.created_at).total_seconds()
        assert abs(delta - ttl) < 2, f"Expected TTL ~{ttl}s, got {delta:.1f}s"

    @pytest.mark.asyncio
    async def test_topic_filter_selects_matching_concept(self):
        """When topic is provided, the concept matching it is targeted."""
        user_id = uuid4()
        kb_id = uuid4()

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [
            WeakConcept(key="oop", label="OOP", due_count=3),
            WeakConcept(key="inheritance", label="Inheritance", due_count=1),
        ]
        retrieval.retrieve_concept_neighborhood.return_value = None
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        chosen_label: list[str] = []

        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            chosen_label.append(ctx.metadata.get("concept_label", ""))
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open",
                reference_answer="R",
                grounding_context="G",
                lesson_id="inheritance",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=AsyncMock(),
            interaction_store=interaction_store,
            quiz_generator=mock_gen,
        )
        await service.start_session(user_id, kb_id, topic="inheritance")

        assert chosen_label and chosen_label[0] == "Inheritance"

    @pytest.mark.asyncio
    async def test_event_published_when_publisher_provided(self):
        """QuizSessionStarted event is published when event_publisher is set."""
        from mindforge.domain.events import QuizSessionStarted

        user_id = uuid4()
        kb_id = uuid4()

        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = None
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()
        event_publisher = AsyncMock()

        async def _fake_execute(ctx: AgentContext) -> AgentResult:
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open",
                reference_answer="R",
                grounding_context="G",
                lesson_id="x",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_fake_execute)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=AsyncMock(),
            interaction_store=interaction_store,
            event_publisher=event_publisher,
            quiz_generator=mock_gen,
        )
        await service.start_session(user_id, kb_id)

        event_publisher.publish_in_tx.assert_called_once()
        published_event = event_publisher.publish_in_tx.call_args[0][0]
        assert isinstance(published_event, QuizSessionStarted)
        assert published_event.user_id == user_id

    @pytest.mark.asyncio
    async def test_kb_prompt_locale_threaded_to_agent_context(self):
        """Regression: KB's prompt_locale must override the default locale on
        the AgentContext.settings handed to QuizGeneratorAgent."""
        retrieval = AsyncMock()
        retrieval.find_weak_concepts.return_value = [_make_weak_concept()]
        retrieval.retrieve_concept_neighborhood.return_value = _make_neighborhood()

        captured_settings = []

        async def _capture(ctx: AgentContext) -> AgentResult:
            captured_settings.append(ctx.settings)
            ctx.metadata["quiz_question"] = QuizQuestion(
                question_id="",
                question_text="Q?",
                question_type="open_ended",
                reference_answer="A",
                grounding_context="C",
                lesson_id="x",
            )
            return AgentResult(success=True, output_key="quiz_question")

        mock_gen = AsyncMock()
        mock_gen.execute = AsyncMock(side_effect=_capture)
        service = _make_service(
            retrieval=retrieval,
            quiz_sessions=AsyncMock(),
            interaction_store=AsyncMock(),
            quiz_generator=mock_gen,
        )
        await service.start_session(uuid4(), uuid4(), prompt_locale="en")

        assert len(captured_settings) == 1
        assert captured_settings[0].prompt_locale == "en"


# ---------------------------------------------------------------------------
# submit_answer tests
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    def _make_session_store(self, session: QuizSession) -> AsyncMock:
        store = AsyncMock()
        store.get_session.return_value = session
        return store

    @pytest.mark.asyncio
    async def test_happy_path_returns_eval_result(self):
        """Happy path: correct session + question → evaluation returned."""
        user_id = uuid4()
        session = _make_session(user_id)
        question = session.questions[0]

        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        async def _fake_eval(ctx: AgentContext) -> AgentResult:
            ctx.metadata["evaluation"] = {
                "score": 4,
                "feedback": "Bardzo dobra odpowiedź",
                "explanation": "Pokrywa główne punkty",
                "quality_flag": "mostly_correct",
            }
            return AgentResult(success=True, output_key="evaluation")

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_fake_eval)
        service = _make_service(
            quiz_sessions=self._make_session_store(session),
            interaction_store=interaction_store,
            study_progress=AsyncMock(),
            quiz_evaluator=mock_eval,
        )
        result = await service.submit_answer(
            user_id,
            session.kb_id,
            session.session_id,
            question.question_id,
            "My answer",
        )

        assert isinstance(result, QuizEvalResult)
        assert result.score == 4
        assert result.feedback == "Bardzo dobra odpowiedź"
        assert result.is_correct is True
        assert result.quality_flag == "mostly_correct"

    @pytest.mark.asyncio
    async def test_result_has_no_sensitive_fields(self):
        """Security invariant: QuizEvalResult must not contain reference_answer
        or grounding_context."""
        user_id = uuid4()
        session = _make_session(
            user_id,
            question_id="qid1",
        )
        # Ensure question has sensitive content we can check for
        session.questions[0].reference_answer = "SUPER_SECRET_ANSWER"
        session.questions[0].grounding_context = "SUPER_SECRET_CONTEXT"

        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        async def _fake_eval(ctx: AgentContext) -> AgentResult:
            # Ensure agent has access to sensitive data but result doesn't expose it
            assert ctx.metadata.get("reference_answer") == "SUPER_SECRET_ANSWER"
            ctx.metadata["evaluation"] = {
                "score": 3,
                "feedback": "OK",
                "explanation": "Fine",
                "quality_flag": None,
            }
            return AgentResult(success=True, output_key="evaluation")

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_fake_eval)
        service = _make_service(
            quiz_sessions=self._make_session_store(session),
            interaction_store=interaction_store,
            study_progress=AsyncMock(),
            quiz_evaluator=mock_eval,
        )
        result = await service.submit_answer(
            user_id, session.kb_id, session.session_id, "qid1", "answer"
        )

        result_dict = result.__dict__
        assert "reference_answer" not in result_dict
        assert "grounding_context" not in result_dict
        assert "SUPER_SECRET_ANSWER" not in str(result_dict)
        assert "SUPER_SECRET_CONTEXT" not in str(result_dict)

    @pytest.mark.asyncio
    async def test_reference_answer_reused_not_regenerated(self):
        """The stored reference_answer from the session is passed to the evaluator
        unchanged — the agent never regenerates it."""
        user_id = uuid4()
        stored_ref = "Stored reference answer — must be reused exactly"
        question = _make_quiz_question(question_id="q1", reference_answer=stored_ref)
        session = QuizSession(
            session_id=uuid4(),
            user_id=user_id,
            kb_id=uuid4(),
            questions=[question],
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=1800),
        )

        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        passed_reference: list[str] = []

        async def _capture_eval(ctx: AgentContext) -> AgentResult:
            passed_reference.append(ctx.metadata.get("reference_answer", ""))
            ctx.metadata["evaluation"] = {
                "score": 3,
                "feedback": "OK",
                "explanation": "",
                "quality_flag": None,
            }
            return AgentResult(success=True, output_key="evaluation")

        store = AsyncMock()
        store.get_session.return_value = session

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_capture_eval)
        service = _make_service(
            quiz_sessions=store,
            interaction_store=interaction_store,
            study_progress=AsyncMock(),
            quiz_evaluator=mock_eval,
        )
        await service.submit_answer(
            user_id, session.kb_id, session.session_id, "q1", "my answer"
        )

        assert passed_reference == [
            stored_ref
        ], "Evaluator must receive the stored reference_answer, not a regenerated one"

    @pytest.mark.asyncio
    async def test_raises_session_not_found(self):
        store = AsyncMock()
        store.get_session.return_value = None

        service = _make_service(quiz_sessions=store)
        with pytest.raises(QuizSessionNotFoundError):
            await service.submit_answer(uuid4(), uuid4(), uuid4(), "qid", "ans")

    @pytest.mark.asyncio
    async def test_raises_access_denied_for_wrong_user(self):
        owner = uuid4()
        attacker = uuid4()
        session = _make_session(owner)

        store = AsyncMock()
        store.get_session.return_value = session

        service = _make_service(quiz_sessions=store)
        with pytest.raises(QuizAccessDeniedError):
            await service.submit_answer(
                attacker,
                session.kb_id,
                session.session_id,
                session.questions[0].question_id,
                "ans",
            )

    @pytest.mark.asyncio
    async def test_raises_access_denied_for_wrong_kb(self):
        """Cross-KB isolation: submit_answer must reject a request where
        kb_id does not match the session's kb_id, even for the correct user."""
        user_id = uuid4()
        session = _make_session(user_id)
        wrong_kb_id = uuid4()  # guaranteed != session.kb_id

        store = AsyncMock()
        store.get_session.return_value = session

        service = _make_service(quiz_sessions=store)
        with pytest.raises(QuizAccessDeniedError):
            await service.submit_answer(
                user_id,
                wrong_kb_id,
                session.session_id,
                session.questions[0].question_id,
                "ans",
            )

    @pytest.mark.asyncio
    async def test_raises_question_not_found(self):
        user_id = uuid4()
        session = _make_session(user_id)

        store = AsyncMock()
        store.get_session.return_value = session

        service = _make_service(quiz_sessions=store)
        with pytest.raises(QuizQuestionNotFoundError):
            await service.submit_answer(
                user_id,
                session.kb_id,
                session.session_id,
                "nonexistent-question-id",
                "ans",
            )

    @pytest.mark.asyncio
    async def test_sr_state_updated_after_evaluation(self):
        """save_review is called with the derived SM-2 rating."""
        user_id = uuid4()
        session = _make_session(user_id, question_id="q42")
        study_progress = AsyncMock()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        async def _fake_eval(ctx: AgentContext) -> AgentResult:
            ctx.metadata["evaluation"] = {
                "score": 5,
                "feedback": "Perfect",
                "explanation": "",
                "quality_flag": "perfect",
            }
            return AgentResult(success=True, output_key="evaluation")

        store = AsyncMock()
        store.get_session.return_value = session

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_fake_eval)
        service = _make_service(
            quiz_sessions=store,
            study_progress=study_progress,
            interaction_store=interaction_store,
            quiz_evaluator=mock_eval,
        )
        await service.submit_answer(
            user_id, session.kb_id, session.session_id, "q42", "perfect answer"
        )

        study_progress.save_review.assert_called_once()
        call_kwargs = study_progress.save_review.call_args
        # positional: (user_id, kb_id, card_id, result)
        passed_result: ReviewResult = call_kwargs[0][3]
        assert passed_result.rating == 5

    @pytest.mark.asyncio
    async def test_session_deleted_after_answer(self):
        """Quiz session is deleted after answer submission."""
        user_id = uuid4()
        session = _make_session(user_id)
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        store = AsyncMock()
        store.get_session.return_value = session

        async def _fake_eval(ctx: AgentContext) -> AgentResult:
            ctx.metadata["evaluation"] = {
                "score": 3,
                "feedback": "OK",
                "explanation": "",
                "quality_flag": None,
            }
            return AgentResult(success=True, output_key="evaluation")

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_fake_eval)
        service = _make_service(
            quiz_sessions=store,
            study_progress=AsyncMock(),
            interaction_store=interaction_store,
            quiz_evaluator=mock_eval,
        )
        await service.submit_answer(
            user_id,
            session.kb_id,
            session.session_id,
            session.questions[0].question_id,
            "ans",
        )

        store.delete_session.assert_called_once_with(session.session_id)

    @pytest.mark.asyncio
    async def test_event_published_after_evaluation(self):
        """QuizAnswerEvaluated event is published when event_publisher is set."""
        from mindforge.domain.events import QuizAnswerEvaluated

        user_id = uuid4()
        session = _make_session(user_id)
        event_publisher = AsyncMock()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        store = AsyncMock()
        store.get_session.return_value = session

        async def _fake_eval(ctx: AgentContext) -> AgentResult:
            ctx.metadata["evaluation"] = {
                "score": 4,
                "feedback": "Good",
                "explanation": "",
                "quality_flag": None,
            }
            return AgentResult(success=True, output_key="evaluation")

        mock_eval = AsyncMock()
        mock_eval.execute = AsyncMock(side_effect=_fake_eval)
        service = _make_service(
            quiz_sessions=store,
            study_progress=AsyncMock(),
            interaction_store=interaction_store,
            event_publisher=event_publisher,
            quiz_evaluator=mock_eval,
        )
        await service.submit_answer(
            user_id,
            session.kb_id,
            session.session_id,
            session.questions[0].question_id,
            "ans",
        )

        event_publisher.publish_in_tx.assert_called_once()
        published_event = event_publisher.publish_in_tx.call_args[0][0]
        assert isinstance(published_event, QuizAnswerEvaluated)
        assert published_event.rating == 4

    @pytest.mark.asyncio
    async def test_is_correct_boundary_at_three(self):
        """is_correct is True for score >= 3, False for score < 3."""
        user_id = uuid4()
        interaction_store = AsyncMock()
        interaction_store.create_interaction.return_value = uuid4()

        for score, expected_correct in [(0, False), (2, False), (3, True), (5, True)]:
            session = _make_session(user_id)
            store = AsyncMock()
            store.get_session.return_value = session

            captured_score = score

            async def _fake_eval(ctx: AgentContext, _s=captured_score) -> AgentResult:
                ctx.metadata["evaluation"] = {
                    "score": _s,
                    "feedback": "",
                    "explanation": "",
                    "quality_flag": None,
                }
                return AgentResult(success=True, output_key="evaluation")

            mock_eval = AsyncMock()
            mock_eval.execute = AsyncMock(side_effect=_fake_eval)
            service = _make_service(
                quiz_sessions=store,
                study_progress=AsyncMock(),
                interaction_store=interaction_store,
                quiz_evaluator=mock_eval,
            )
            result = await service.submit_answer(
                user_id,
                session.kb_id,
                session.session_id,
                session.questions[0].question_id,
                "ans",
            )

            assert (
                result.is_correct is expected_correct
            ), f"score={score}: expected is_correct={expected_correct}, got {result.is_correct}"


# ---------------------------------------------------------------------------
# Neighbourhood context serialisation
# ---------------------------------------------------------------------------


class TestNeighborhoodToContext:
    def test_includes_concept_label_and_definition(self):
        nh = _make_neighborhood()
        ctx = _neighborhood_to_context(nh)
        assert "Python OOP" in ctx
        assert "Object-oriented programming" in ctx

    def test_includes_facts(self):
        nh = _make_neighborhood()
        ctx = _neighborhood_to_context(nh)
        assert "Classes define object structure" in ctx

    def test_includes_neighbors(self):
        nh = _make_neighborhood()
        ctx = _neighborhood_to_context(nh)
        assert "Inheritance" in ctx
        assert "EXTENDS" in ctx

    def test_empty_neighborhood_still_returns_string(self):
        nh = ConceptNeighborhood(
            center=ConceptNode(key="k", label="Label", description=""),
            neighbors=[],
            depth=1,
        )
        ctx = _neighborhood_to_context(nh)
        assert "Label" in ctx
