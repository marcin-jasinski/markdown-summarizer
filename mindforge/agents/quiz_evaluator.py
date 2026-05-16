"""
QuizEvaluator agent — evaluates a student's answer against the stored
reference answer and grounding context.

Security: Never regenerates the reference answer — reuses what is stored in
the quiz session.  This prevents cost escalation and ensures server-authoritative
grading (the client never sees reference_answer or grounding_context).
"""

from __future__ import annotations

import json
import logging
import time

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import (
    CostTier,
    DeadlineProfile,
    ModelTier,
    ReviewResult,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="quiz_evaluator",
    description="Evaluates student answers against stored reference answers.",
    input_types=("student_answer", "reference_answer", "grounding_context"),
    output_types=("evaluation",),
    required_model_tier=ModelTier.LARGE,
    estimated_cost_tier=CostTier.MEDIUM,
)

_VALID_QUALITY_FLAGS = frozenset(
    {None, "too_short", "off_topic", "mostly_correct", "perfect"}
)


class QuizEvaluatorAgent:
    """Evaluates a student answer and returns a score + feedback."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                quiz_evaluator as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "quiz_evaluator"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        question_text: str = context.metadata.get("question_text", "")
        reference_answer: str = context.metadata.get("reference_answer", "")
        grounding_context: str = context.metadata.get("grounding_context", "")
        student_answer: str = context.metadata.get("student_answer", "")

        if not reference_answer:
            return AgentResult(
                success=False,
                output_key="evaluation",
                error="reference_answer not available — cannot evaluate without stored reference.",
            )
        if not student_answer:
            return AgentResult(
                success=False,
                output_key="evaluation",
                error="student_answer not provided.",
            )

        locale = context.settings.prompt_locale
        user_message = self._prompts.user_template(locale).format(
            question_text=question_text,
            reference_answer=reference_answer,
            grounding_context=grounding_context,
            student_answer=student_answer,
        )

        model = context.settings.model_for_tier(ModelTier.LARGE)
        messages = [
            {"role": "system", "content": self._prompts.system_prompt(locale)},
            {"role": "user", "content": user_message},
        ]

        try:
            result = await context.gateway.complete(
                model=model,
                messages=messages,
                deadline=DeadlineProfile.INTERACTIVE,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            log.exception("QuizEvaluatorAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="evaluation",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            data = json.loads(result.content)
            score = int(data.get("score", 0))
            score = max(0, min(5, score))  # clamp to SM-2 range

            quality_flag = data.get("quality_flag")
            if quality_flag not in _VALID_QUALITY_FLAGS:
                quality_flag = None

            evaluation = {
                "score": score,
                "feedback": str(data.get("feedback", "")),
                "explanation": str(data.get("explanation", "")),
                "missing_points": [str(p) for p in data.get("missing_points", [])],
                "quality_flag": quality_flag,
                "review_result": ReviewResult(rating=score, quality_flag=quality_flag),
            }
            context.metadata["evaluation"] = evaluation

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            log.warning("QuizEvaluatorAgent failed to parse LLM response: %s", exc)
            return AgentResult(
                success=False,
                output_key="evaluation",
                error=f"Response parse error: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="evaluation",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
