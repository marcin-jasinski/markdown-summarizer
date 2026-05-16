"""
FlashcardGenerator agent — produces study flashcards (BASIC, CLOZE, REVERSE)
from the document summary and cleaned content.

Card IDs are deterministically computed via sha256(kb_id|lesson_id|card_type|front|back)[:16]
as defined on FlashcardData.__post_init__.
"""

from __future__ import annotations

import json
import logging
import time

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import (
    CardType,
    CostTier,
    DeadlineProfile,
    FlashcardData,
    ModelTier,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="flashcard_generator",
    description="Generates BASIC, CLOZE, and REVERSE study flashcards from document summary.",
    input_types=("summary", "cleaned_content"),
    output_types=("flashcards",),
    required_model_tier=ModelTier.LARGE,
    estimated_cost_tier=CostTier.MEDIUM,
)

_CARD_TYPE_MAP: dict[str, CardType] = {
    "BASIC": CardType.BASIC,
    "CLOZE": CardType.CLOZE,
    "REVERSE": CardType.REVERSE,
}

# Truncate document content for card generation to control costs
_MAX_CONTENT_CHARS = 20_000


class FlashcardGeneratorAgent:
    """Produces ``flashcards`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                flashcard_gen as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "flashcard_generator"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        summary = context.artifact.summary
        if summary is None:
            return AgentResult(
                success=False,
                output_key="flashcards",
                error="Summary not available; FlashcardGenerator requires Summarizer to run first.",
            )

        content: str = context.metadata.get(
            "cleaned_content",
            context.metadata.get("original_content", ""),
        )

        locale = context.settings.prompt_locale
        key_points_text = "\n".join(f"- {p}" for p in summary.key_points)
        user_message = self._prompts.user_template(locale).format(
            summary=summary.summary,
            key_points=key_points_text,
            content_excerpt=content[:_MAX_CONTENT_CHARS],
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
                deadline=DeadlineProfile.BATCH,
                temperature=0.4,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            log.exception("FlashcardGeneratorAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="flashcards",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        flashcards: list[FlashcardData] = []
        try:
            raw = json.loads(result.content)
            # Model may return a top-level array or an object with an array field
            if isinstance(raw, list):
                card_list = raw
            elif isinstance(raw, dict):
                # Try common wrapper keys
                card_list = raw.get("flashcards", raw.get("cards", []))
            else:
                card_list = []

            for card_data in card_list:
                card_type_str = str(card_data.get("card_type", "BASIC")).upper()
                card_type = _CARD_TYPE_MAP.get(card_type_str, CardType.BASIC)
                front = str(card_data.get("front", "")).strip()
                back = str(card_data.get("back", "")).strip()
                tags = [str(t) for t in card_data.get("tags", [])]

                if not front or not back:
                    continue

                flashcards.append(
                    FlashcardData(
                        kb_id=context.knowledge_base_id,
                        lesson_id=context.artifact.lesson_id,
                        card_type=card_type,
                        front=front,
                        back=back,
                        tags=tags,
                    )
                )
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            log.warning("FlashcardGeneratorAgent failed to parse LLM response: %s", exc)

        context.artifact.flashcards = flashcards

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="flashcards",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
