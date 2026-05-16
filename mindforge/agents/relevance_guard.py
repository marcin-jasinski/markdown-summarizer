"""
RelevanceGuard agent — validates that a document's content is relevant to the
existing knowledge base before allowing expensive downstream processing.

For empty knowledge bases (first document), always accepts.  For populated
KBs, uses a SMALL-tier model to compare the document's topics against the
existing concept profile.
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
    ValidationResult,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="relevance_guard",
    description="Validates document relevance against the knowledge base concept profile.",
    input_types=("original_content",),
    output_types=("validation_result",),
    required_model_tier=ModelTier.SMALL,
    estimated_cost_tier=CostTier.LOW,
)

_RELEVANCE_THRESHOLD = 0.4


class RelevanceGuardAgent:
    """Produces ``validation_result`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                relevance_guard as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "relevance_guard"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        content: str = context.metadata.get("original_content", "")
        if not content:
            return AgentResult(
                success=False,
                output_key="validation_result",
                error="original_content not available in agent context metadata",
            )

        # Retrieve existing concepts from the knowledge base graph
        existing_concepts: list[str] = []
        try:
            concepts = await context.retrieval.get_concepts(context.knowledge_base_id)
            existing_concepts = [c.label for c in concepts]
        except Exception as exc:
            log.warning("RelevanceGuard could not retrieve concepts: %s", exc)

        # Empty KB → always accept
        if not existing_concepts:
            context.artifact.validation_result = ValidationResult(
                is_relevant=True,
                confidence=1.0,
                reason="Knowledge base is empty; first document is always accepted.",
            )
            return AgentResult(
                success=True,
                output_key="validation_result",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        model = context.settings.model_for_tier(ModelTier.SMALL)
        concept_list = ", ".join(existing_concepts[:50])  # cap to avoid token explosion
        excerpt = content[:3000]  # first 3000 chars for relevance check

        user_message = (
            f"Existing concepts in knowledge base: {concept_list}\n\n"
            f"Document excerpt:\n{excerpt}"
        )

        messages = [
            {
                "role": "system",
                "content": self._prompts.system_prompt(context.settings.prompt_locale),
            },
            {"role": "user", "content": user_message},
        ]

        try:
            result = await context.gateway.complete(
                model=model,
                messages=messages,
                deadline=DeadlineProfile.INTERACTIVE,
                temperature=0.1,
            )
        except Exception as exc:
            log.exception("RelevanceGuardAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="validation_result",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            data = json.loads(result.content)
            validation = ValidationResult(
                is_relevant=bool(data.get("is_relevant", True)),
                confidence=float(data.get("confidence", 1.0)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            log.warning("RelevanceGuard failed to parse LLM response: %s", exc)
            # On parse failure, default to accepting the document
            validation = ValidationResult(
                is_relevant=True,
                confidence=0.5,
                reason="Relevance check parse error; defaulting to accept.",
            )

        context.artifact.validation_result = validation

        if not validation.is_relevant and validation.confidence >= _RELEVANCE_THRESHOLD:
            return AgentResult(
                success=False,
                output_key="validation_result",
                tokens_used=result.input_tokens + result.output_tokens,
                cost_usd=result.cost_usd,
                duration_ms=(time.monotonic() - start) * 1000,
                error=f"Document rejected: {validation.reason}",
            )

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="validation_result",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
