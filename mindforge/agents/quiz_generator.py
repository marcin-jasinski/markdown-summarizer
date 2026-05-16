"""
QuizGenerator agent — generates quiz questions at quiz runtime (not in the
pipeline).

Takes a concept neighborhood retrieved via Graph RAG and produces a question
with a reference answer and grounding context.  Used only at question-generation
time, not during document processing.
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
    QuizQuestion,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="quiz_generator",
    description="Generates quiz questions from Graph RAG concept neighbourhoods.",
    input_types=("concept_neighborhood",),
    output_types=("quiz_question",),
    required_model_tier=ModelTier.LARGE,
    estimated_cost_tier=CostTier.MEDIUM,
)


class QuizGeneratorAgent:
    """Generates a single quiz question from the retrieval context in metadata."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                quiz_generator as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "quiz_generator"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        concept_label: str = context.metadata.get("concept_label", "")
        retrieval_context: str = context.metadata.get("retrieval_context", "")

        if not retrieval_context:
            return AgentResult(
                success=False,
                output_key="quiz_question",
                error="retrieval_context not available in agent context metadata",
            )

        locale = context.settings.prompt_locale
        user_message = self._prompts.user_template(locale).format(
            concept_label=concept_label or "unknown",
            retrieval_context=retrieval_context,
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
                temperature=0.5,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            log.exception("QuizGeneratorAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="quiz_question",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            data = json.loads(result.content)
            question = QuizQuestion(
                question_id="",  # assigned by caller after deterministic hashing
                question_text=str(data.get("question_text", "")),
                question_type=str(data.get("question_type", "open_ended")),
                reference_answer=str(data.get("reference_answer", "")),
                grounding_context=str(data.get("grounding_context", retrieval_context)),
                lesson_id=context.artifact.lesson_id,
            )
            context.metadata["quiz_question"] = question
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning("QuizGeneratorAgent failed to parse LLM response: %s", exc)
            return AgentResult(
                success=False,
                output_key="quiz_question",
                error=f"Response parse error: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="quiz_question",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
