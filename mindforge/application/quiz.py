"""
Application layer — Quiz Service.

Server-authoritative quiz session management. ``reference_answer`` and
``grounding_context`` are stored server-side inside :class:`QuizSession` and
are NEVER exposed to the client.

Architecture:
  - Uses Graph RAG to target weak concepts (graph-first, then SR state).
  - Delegates question generation to :class:`~mindforge.agents.quiz_generator.QuizGeneratorAgent`.
  - Delegates answer evaluation to :class:`~mindforge.agents.quiz_evaluator.QuizEvaluatorAgent`.
  - Reuses the stored ``reference_answer`` — never regenerates it.
  - Records every interaction turn for the audit trail.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from mindforge.domain.agents import Agent, AgentContext, ProcessingSettings
from mindforge.domain.events import QuizAnswerEvaluated, QuizSessionStarted
from mindforge.domain.models import (
    DocumentArtifact,
    QuizQuestion,
    QuizSession,
    ReviewResult,
)
from mindforge.domain.ports import (
    AIGateway,
    EventPublisher,
    InteractionStore,
    QuizSessionStore,
    RetrievalPort,
    StudyProgressStore,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result types (no sensitive fields)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuizStartResult:
    """Returned by :meth:`QuizService.start_session`.

    Deliberately excludes ``reference_answer`` and ``grounding_context``.
    """

    session_id: UUID
    question_id: str
    question_text: str
    question_type: str
    lesson_id: str


@dataclass(frozen=True)
class QuizEvalResult:
    """Returned by :meth:`QuizService.submit_answer`.

    Deliberately excludes ``reference_answer`` and ``grounding_context``.
    """

    question_id: str
    score: int  # SM-2 rating 0–5
    feedback: str
    explanation: str
    is_correct: bool  # score >= 3
    quality_flag: str | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NoWeakConceptsError(RuntimeError):
    """No weak concepts found — the KB has no processed documents yet."""


class QuizSessionNotFoundError(LookupError):
    """Session does not exist or has expired."""


class QuizQuestionNotFoundError(LookupError):
    """Question ID not found inside this session."""


class QuizAccessDeniedError(PermissionError):
    """Caller does not own this quiz session."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class QuizService:
    """Orchestrates the full quiz lifecycle with server-authoritative grading.

    Parameters
    ----------
    gateway:
        AI gateway used to drive :class:`QuizGeneratorAgent` and
        :class:`QuizEvaluatorAgent`.
    retrieval:
        Graph RAG retrieval port — provides weak-concept targeting and
        concept-neighbourhood context.
    quiz_sessions:
        Session store (Redis or PostgreSQL fallback).
    study_progress:
        Spaced-repetition store for SM-2 scheduling.
    interaction_store:
        Audit-trail store for recording quiz interactions.
    settings:
        Processing settings carrying model-tier mappings.
    event_publisher:
        Optional outbox publisher.  When provided, ``QuizSessionStarted``
        and ``QuizAnswerEvaluated`` events are written to the outbox.
    quiz_ttl_seconds:
        Session lifetime in seconds (default 1800 = 30 min).
    """

    def __init__(
        self,
        gateway: AIGateway,
        retrieval: RetrievalPort,
        quiz_sessions: QuizSessionStore,
        study_progress: StudyProgressStore,
        interaction_store: InteractionStore,
        settings: ProcessingSettings,
        *,
        quiz_generator: Agent,
        quiz_evaluator: Agent,
        event_publisher: EventPublisher | None = None,
        quiz_ttl_seconds: int = 1800,
    ) -> None:
        self._gateway = gateway
        self._retrieval = retrieval
        self._quiz_sessions = quiz_sessions
        self._study_progress = study_progress
        self._interaction_store = interaction_store
        self._settings = settings
        self._event_publisher = event_publisher
        self._quiz_ttl_seconds = quiz_ttl_seconds
        self._quiz_generator = quiz_generator
        self._quiz_evaluator = quiz_evaluator

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def start_session(
        self,
        user_id: UUID,
        kb_id: UUID,
        topic: str | None = None,
        *,
        prompt_locale: str | None = None,
    ) -> QuizStartResult:
        """Start a new quiz session targeting the user's weakest concepts.

        Steps:
        1. Query weak concepts via Graph RAG.
        2. Select target concept (optionally filtered by *topic*).
        3. Retrieve concept neighbourhood for grounding context.
        4. Call :class:`QuizGeneratorAgent` to produce question + reference answer.
        5. Persist session server-side (reference_answer stored securely).
        6. Record audit interaction turn.
        7. Publish ``QuizSessionStarted`` domain event.
        8. Return :class:`QuizStartResult` (NO reference_answer, NO grounding_context).

        Raises
        ------
        NoWeakConceptsError
            When no weak concepts exist (KB has no processed documents).
        RuntimeError
            When the question-generation agent fails.
        """
        # Step 1: find weak concepts via Graph RAG
        today = date.today()
        weak_concepts = await self._retrieval.find_weak_concepts(
            user_id, kb_id, today, limit=5
        )
        if not weak_concepts:
            raise NoWeakConceptsError(
                "Brak dostępnych konceptów do quizu. Dodaj i przetwórz dokumenty."
            )

        # Step 2: select target concept (weakest first), optionally filter by topic
        target = weak_concepts[0]
        if topic:
            filtered = [w for w in weak_concepts if topic.lower() in w.label.lower()]
            if filtered:
                target = filtered[0]

        # Step 3: retrieve concept neighbourhood for grounding context
        neighborhood = await self._retrieval.retrieve_concept_neighborhood(
            kb_id, target.key, depth=2
        )
        retrieval_context = (
            _neighborhood_to_context(neighborhood) if neighborhood else target.label
        )

        # Step 4: generate question via QuizGeneratorAgent
        session_id = uuid4()
        dummy_artifact = _make_dummy_artifact(kb_id, target.key)
        agent_settings = (
            dataclasses.replace(self._settings, prompt_locale=prompt_locale)
            if prompt_locale
            else self._settings
        )
        ctx = AgentContext(
            document_id=dummy_artifact.document_id,
            knowledge_base_id=kb_id,
            artifact=dummy_artifact,
            gateway=self._gateway,
            retrieval=self._retrieval,
            settings=agent_settings,
            tracer=None,
            metadata={
                "concept_label": target.label,
                "retrieval_context": retrieval_context,
                "lesson_id": target.key,
            },
        )
        agent = self._quiz_generator
        agent_result = await agent.execute(ctx)
        if not agent_result.success:
            raise RuntimeError(
                f"Nie udało się wygenerować pytania quizowego: {agent_result.error}"
            )

        q_raw: QuizQuestion | None = ctx.metadata.get("quiz_question")
        if q_raw is None:
            raise RuntimeError("Agent nie zwrócił pytania.")

        # Step 5: assign deterministic question_id and build full QuizQuestion
        question_id = hashlib.sha256(f"{session_id}:0".encode()).hexdigest()[:16]
        question = QuizQuestion(
            question_id=question_id,
            question_text=q_raw.question_text,
            question_type=q_raw.question_type,
            reference_answer=q_raw.reference_answer,  # stored server-side
            grounding_context=q_raw.grounding_context,  # stored server-side
            lesson_id=q_raw.lesson_id or target.key,
        )

        # Step 6: persist session with reference_answer stored securely
        now = datetime.now(timezone.utc)
        session = QuizSession(
            session_id=session_id,
            user_id=user_id,
            kb_id=kb_id,
            questions=[question],
            created_at=now,
            expires_at=datetime.fromtimestamp(
                now.timestamp() + self._quiz_ttl_seconds, tz=timezone.utc
            ),
        )
        await self._quiz_sessions.create_session(session)

        # Step 7: record audit interaction
        await self._record_quiz_start(user_id, kb_id, session_id, question)

        # Step 8: publish domain event
        if self._event_publisher is not None:
            await self._event_publisher.publish_in_tx(
                QuizSessionStarted(
                    session_id=session_id,
                    user_id=user_id,
                    knowledge_base_id=kb_id,
                    question_count=1,
                    timestamp=now,
                ),
                None,
            )

        # Return result WITHOUT reference_answer or grounding_context
        return QuizStartResult(
            session_id=session_id,
            question_id=question.question_id,
            question_text=question.question_text,
            question_type=question.question_type,
            lesson_id=question.lesson_id,
        )

    async def submit_answer(
        self,
        user_id: UUID,
        kb_id: UUID,
        session_id: UUID,
        question_id: str,
        user_answer: str,
        *,
        prompt_locale: str | None = None,
    ) -> QuizEvalResult:
        """Evaluate a user answer server-side.

        Steps:
        1. Load session — raise if not found or expired.
        2. Validate session ownership — raise if wrong user.
        3. Locate the question by *question_id*.
        4. Call :class:`QuizEvaluatorAgent` with stored ``reference_answer``
           and ``grounding_context`` (never regenerated).
        5. Update SM-2 schedule via ``StudyProgressStore``.
        6. Record audit interaction turn.
        7. Publish ``QuizAnswerEvaluated`` domain event.
        8. Delete session.
        9. Return :class:`QuizEvalResult` (NO reference_answer, NO grounding_context).

        Raises
        ------
        QuizSessionNotFoundError
            When the session does not exist or has expired.
        QuizAccessDeniedError
            When the session belongs to a different user.
        QuizQuestionNotFoundError
            When *question_id* is not found in the session.
        RuntimeError
            When the evaluation agent fails.
        """
        # Step 1: load session
        session = await self._quiz_sessions.get_session(session_id)
        if session is None:
            raise QuizSessionNotFoundError("Sesja quizu nie istnieje lub wygasła.")

        # Step 2: validate ownership and KB scope
        if session.user_id != user_id:
            raise QuizAccessDeniedError("Brak dostępu do tej sesji.")
        if session.kb_id != kb_id:
            raise QuizAccessDeniedError("Sesja należy do innej bazy wiedzy.")

        # Step 3: find question
        question = next(
            (q for q in session.questions if q.question_id == question_id), None
        )
        if question is None:
            raise QuizQuestionNotFoundError("Pytanie nie istnieje w tej sesji.")

        # Step 4: evaluate via QuizEvaluatorAgent (reuses stored reference_answer)
        dummy_artifact = _make_dummy_artifact(kb_id, question.lesson_id)
        agent_settings = (
            dataclasses.replace(self._settings, prompt_locale=prompt_locale)
            if prompt_locale
            else self._settings
        )
        ctx = AgentContext(
            document_id=dummy_artifact.document_id,
            knowledge_base_id=kb_id,
            artifact=dummy_artifact,
            gateway=self._gateway,
            retrieval=self._retrieval,
            settings=agent_settings,
            tracer=None,
            metadata={
                "question_text": question.question_text,
                "reference_answer": question.reference_answer,  # from server-side store
                "grounding_context": question.grounding_context,  # from server-side store
                "student_answer": user_answer,
            },
        )
        eval_agent = self._quiz_evaluator
        eval_result = await eval_agent.execute(ctx)
        if not eval_result.success:
            raise RuntimeError(f"Nie udało się ocenić odpowiedzi: {eval_result.error}")

        evaluation: dict[str, Any] = ctx.metadata.get("evaluation", {})
        score: int = max(0, min(5, int(evaluation.get("score", 0))))
        feedback: str = str(evaluation.get("feedback", ""))
        explanation: str = str(evaluation.get("explanation", ""))
        quality_flag: str | None = evaluation.get("quality_flag")

        # Step 5: update spaced-repetition schedule
        await self._study_progress.save_review(
            user_id,
            kb_id,
            question.question_id,
            ReviewResult(rating=score, quality_flag=quality_flag),
        )

        # Step 6: record audit interaction
        now = datetime.now(timezone.utc)
        await self._record_quiz_answer(
            user_id, kb_id, session_id, question_id, score, feedback, now
        )

        # Step 7: publish domain event
        if self._event_publisher is not None:
            await self._event_publisher.publish_in_tx(
                QuizAnswerEvaluated(
                    session_id=session_id,
                    user_id=user_id,
                    question_id=question_id,
                    rating=score,
                    timestamp=now,
                ),
                None,
            )

        # Step 8: clean up session after answer
        await self._quiz_sessions.delete_session(session_id)

        # Return result — NO reference_answer, NO grounding_context
        return QuizEvalResult(
            question_id=question_id,
            score=score,
            feedback=feedback,
            explanation=explanation,
            is_correct=score >= 3,
            quality_flag=quality_flag,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _record_quiz_start(
        self,
        user_id: UUID,
        kb_id: UUID,
        session_id: UUID,
        question: QuizQuestion,
    ) -> None:
        """Record quiz session start in the interaction audit trail."""
        try:
            interaction_id = await self._interaction_store.create_interaction(
                interaction_type="quiz",
                user_id=user_id,
                kb_id=kb_id,
                context={"session_id": str(session_id)},
            )
            await self._interaction_store.add_turn(
                interaction_id,
                actor_type="system",
                actor_id="quiz_service",
                action="question_generated",
                output_data={
                    "question_id": question.question_id,
                    "question_type": question.question_type,
                    "lesson_id": question.lesson_id,
                    # reference_answer and grounding_context are deliberately excluded
                },
            )
        except Exception:
            log.exception("Failed to record quiz start audit turn")

    async def _record_quiz_answer(
        self,
        user_id: UUID,
        kb_id: UUID,
        session_id: UUID,
        question_id: str,
        score: int,
        feedback: str,
        timestamp: datetime,
    ) -> None:
        """Record quiz answer evaluation in the interaction audit trail."""
        try:
            interaction_id = await self._interaction_store.create_interaction(
                interaction_type="quiz_evaluation",
                user_id=user_id,
                kb_id=kb_id,
                context={
                    "session_id": str(session_id),
                    "question_id": question_id,
                },
            )
            await self._interaction_store.add_turn(
                interaction_id,
                actor_type="system",
                actor_id="quiz_service",
                action="answer_evaluated",
                output_data={
                    "score": score,
                    "feedback": feedback,
                    # reference_answer and grounding_context deliberately excluded
                },
            )
        except Exception:
            log.exception("Failed to record quiz answer audit turn")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _neighborhood_to_context(neighborhood: Any) -> str:
    """Convert a ``ConceptNeighborhood`` to a plaintext context string.

    Produces a structured summary consumed by :class:`QuizGeneratorAgent`
    via the ``retrieval_context`` metadata key.
    """
    parts: list[str] = [f"Concept: {neighborhood.center.label}"]
    if neighborhood.center.description:
        parts.append(f"Definition: {neighborhood.center.description}")

    if neighborhood.facts:
        parts.append("\nKey facts:")
        for fact in neighborhood.facts:
            parts.append(f"- {fact}")

    if neighborhood.neighbors:
        parts.append("\nRelated concepts:")
        for nb in neighborhood.neighbors:
            desc = f": {nb.description}" if getattr(nb, "description", "") else ""
            parts.append(f"- {nb.label} ({nb.relation}){desc}")

    return "\n".join(parts)


def _make_dummy_artifact(kb_id: UUID, lesson_id: str) -> DocumentArtifact:
    """Build a minimal :class:`DocumentArtifact` for quiz-time agent execution.

    Quiz agents (generator and evaluator) are not tied to a specific pipeline
    artifact; a lightweight placeholder satisfies the ``AgentContext`` contract.
    """
    return DocumentArtifact(
        document_id=uuid4(),
        knowledge_base_id=kb_id,
        lesson_id=lesson_id,
        version=1,
        created_at=datetime.now(timezone.utc),
    )
