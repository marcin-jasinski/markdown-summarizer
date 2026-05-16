"""
ImageAnalyzer agent — describes embedded images using a VISION-tier model.

Produces ``image_descriptions`` in the artifact so that downstream agents
(Summarizer, FlashcardGenerator) can incorporate visual content.
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import (
    CostTier,
    DeadlineProfile,
    ImageDescription,
    ModelTier,
)

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="image_analyzer",
    description="Describes images and diagrams from the document using a vision model.",
    input_types=("embedded_images",),
    output_types=("image_descriptions",),
    required_model_tier=ModelTier.VISION,
    estimated_cost_tier=CostTier.MEDIUM,
)


class ImageAnalyzerAgent:
    """Produces ``image_descriptions`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                image_analyzer as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "image_analyzer"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        if not context.settings.enable_image_analysis:
            return AgentResult(
                success=True,
                output_key="image_descriptions",
                error=None,
            )

        embedded_images: list[bytes] = context.metadata.get("embedded_images", [])
        if not embedded_images:
            # No images to process — succeed silently
            context.artifact.image_descriptions = []
            return AgentResult(
                success=True,
                output_key="image_descriptions",
            )

        model = context.settings.model_for_tier(ModelTier.VISION)
        descriptions: list[ImageDescription] = []
        total_tokens = 0
        total_cost = 0.0

        for idx, image_bytes in enumerate(embedded_images):
            media_ref = f"image_{idx}"
            b64 = base64.b64encode(image_bytes).decode("ascii")

            messages = [
                {
                    "role": "system",
                    "content": self._prompts.system_prompt(
                        context.settings.prompt_locale
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": "Describe this image in an educational context.",
                        },
                    ],
                },
            ]

            try:
                result = await context.gateway.complete(
                    model=model,
                    messages=messages,
                    deadline=DeadlineProfile.BATCH,
                    temperature=0.2,
                )
            except Exception as exc:
                log.warning("ImageAnalyzerAgent failed for image %d: %s", idx, exc)
                descriptions.append(
                    ImageDescription(
                        media_ref=media_ref,
                        description="[Image analysis failed]",
                        alt_text="",
                    )
                )
                continue

            descriptions.append(
                ImageDescription(
                    media_ref=media_ref,
                    description=result.content,
                    alt_text=result.content[:120],
                )
            )
            total_tokens += result.input_tokens + result.output_tokens
            total_cost += result.cost_usd

        context.artifact.image_descriptions = descriptions

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="image_descriptions",
            tokens_used=total_tokens,
            cost_usd=total_cost,
            duration_ms=duration_ms,
        )
