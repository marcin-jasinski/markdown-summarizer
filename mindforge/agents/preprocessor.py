"""
Preprocessor agent — cleans raw document text before summarisation.

Removes headers, footers, TOC entries, and boilerplate using a SMALL-tier
language model so downstream agents receive clean, structured input.
"""

from __future__ import annotations

import logging
import time

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import CostTier, DeadlineProfile, ModelTier

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="preprocessor",
    description="Cleans raw document text by removing noise and normalising formatting.",
    input_types=("original_content",),
    output_types=("cleaned_content",),
    required_model_tier=ModelTier.SMALL,
    estimated_cost_tier=CostTier.LOW,
)


class PreprocessorAgent:
    """Produces ``cleaned_content`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                preprocessor as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "preprocessor"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        # original_content is injected into metadata by the pipeline worker
        content: str = context.metadata.get("original_content", "")
        if not content:
            return AgentResult(
                success=False,
                output_key="cleaned_content",
                error="original_content not available in agent context metadata",
            )

        locale = context.settings.prompt_locale
        model = context.settings.model_for_tier(ModelTier.SMALL)
        messages = [
            {"role": "system", "content": self._prompts.system_prompt(locale)},
            {"role": "user", "content": content},
        ]

        try:
            result = await context.gateway.complete(
                model=model,
                messages=messages,
                deadline=DeadlineProfile.BATCH,
                temperature=0.1,
            )
        except Exception as exc:
            log.exception("PreprocessorAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="cleaned_content",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # Store cleaned content in artifact metadata (no dedicated field on artifact yet)
        context.metadata["cleaned_content"] = result.content

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="cleaned_content",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
