"""
Summarizer agent — generates a structured educational summary with key points
and topics from the cleaned document content.

Uses LARGE-tier model with structured JSON output.  Incorporates image
descriptions, fetched articles, and prior KB concepts as context.
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
    SummaryData,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="summarizer",
    description="Generates a structured educational summary with key points and topics.",
    input_types=("cleaned_content", "image_descriptions", "fetched_articles"),
    output_types=("summary",),
    required_model_tier=ModelTier.LARGE,
    estimated_cost_tier=CostTier.MEDIUM,
)

# Maximum content length sent to the model (characters)
_MAX_CONTENT_CHARS = 60_000


class SummarizerAgent:
    """Produces ``summary`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                summarizer as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "summarizer"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        content: str = context.metadata.get(
            "cleaned_content",
            context.metadata.get("original_content", ""),
        )
        if not content:
            return AgentResult(
                success=False,
                output_key="summary",
                error="No content available for summarisation",
            )

        # Build optional context sections
        locale = context.settings.prompt_locale
        image_context = ""
        if context.artifact.image_descriptions:
            descriptions_text = "\n".join(
                f"- {img.description}" for img in context.artifact.image_descriptions
            )
            image_context = self._prompts.image_context_template(locale).format(
                descriptions=descriptions_text
            )

        article_context = ""
        if context.artifact.fetched_articles:
            articles_text = "\n\n".join(
                f"[{art.title}] ({art.url})\n{art.content[:2000]}"
                for art in context.artifact.fetched_articles
                if art.content
            )
            article_context = self._prompts.article_context_template(locale).format(
                articles=articles_text
            )

        prior_concepts_context = ""
        prior_concepts: list[str] = context.metadata.get("prior_concepts", [])
        if prior_concepts:
            prior_concepts_context = self._prompts.prior_concepts_template(
                locale
            ).format(concepts=", ".join(prior_concepts[:50]))

        user_message = self._prompts.user_template(locale).format(
            content=content[:_MAX_CONTENT_CHARS],
            image_context=image_context,
            article_context=article_context,
            prior_concepts_context=prior_concepts_context,
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
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            log.exception("SummarizerAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="summary",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            data = json.loads(result.content)
            summary = SummaryData(
                summary=str(data.get("summary", "")),
                key_points=[str(p) for p in data.get("key_points", [])],
                topics=[str(t) for t in data.get("topics", [])],
            )
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning("SummarizerAgent failed to parse LLM response: %s", exc)
            # Graceful degradation — store raw content as summary
            summary = SummaryData(
                summary=result.content[:2000],
                key_points=[],
                topics=[],
            )

        context.artifact.summary = summary

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="summary",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
