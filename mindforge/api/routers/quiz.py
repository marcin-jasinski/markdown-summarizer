"""Quiz router — server-authoritative session management and answer evaluation.

Security: reference_answer and grounding_context are NEVER sent to the client.
All grading is done server-side via QuizService (application layer).
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mindforge.api.deps import (
    get_current_user,
    get_kb_repo,
    get_quiz_service,
)
from mindforge.api.schemas import (
    AnswerEvaluationResponse,
    QuizQuestionResponse,
    StartQuizRequest,
    SubmitAnswerRequest,
)
from mindforge.application.quiz import (
    NoWeakConceptsError,
    QuizAccessDeniedError,
    QuizQuestionNotFoundError,
    QuizService,
    QuizSessionNotFoundError,
)
from mindforge.domain.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/quiz", tags=["quiz"])


@router.post("/start", response_model=QuizQuestionResponse)
async def start_quiz(
    kb_id: UUID,
    payload: StartQuizRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    quiz_service: Annotated[QuizService, Depends(get_quiz_service)],
) -> QuizQuestionResponse:
    """Start a new quiz session and return the first question (no sensitive fields)."""
    kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    try:
        result = await quiz_service.start_session(
            user_id=current_user.user_id,
            kb_id=kb_id,
            topic=payload.topic,
            prompt_locale=kb.prompt_locale,
        )
    except NoWeakConceptsError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError:
        log.exception(
            "Quiz start failed for user=%s kb=%s", current_user.user_id, kb_id
        )
        raise HTTPException(
            status_code=500, detail="Nie udało się wygenerować pytania."
        )

    return QuizQuestionResponse(
        session_id=result.session_id,
        question_id=result.question_id,
        question_text=result.question_text,
        question_type=result.question_type,
        lesson_id=result.lesson_id,
    )


@router.post("/{session_id}/answer", response_model=AnswerEvaluationResponse)
async def submit_answer(
    kb_id: UUID,
    session_id: UUID,
    payload: SubmitAnswerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[object, Depends(get_kb_repo)],
    quiz_service: Annotated[QuizService, Depends(get_quiz_service)],
) -> AnswerEvaluationResponse:
    """Server-authoritative answer evaluation. Never exposes reference_answer."""
    kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    try:
        result = await quiz_service.submit_answer(
            user_id=current_user.user_id,
            kb_id=kb_id,
            session_id=session_id,
            question_id=payload.question_id,
            user_answer=payload.user_answer,
            prompt_locale=kb.prompt_locale,
        )
    except QuizSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except QuizAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except QuizQuestionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError:
        log.exception("Quiz evaluation failed for session=%s", session_id)
        raise HTTPException(status_code=500, detail="Nie udało się ocenić odpowiedzi.")

    return AnswerEvaluationResponse(
        question_id=result.question_id,
        score=result.score,
        feedback=result.feedback,
        is_correct=result.is_correct,
    )
