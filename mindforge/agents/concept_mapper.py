"""
ConceptMapper agent — extracts a concept map (named concepts + directed
relationships) from the document summary and cleaned content.

Concepts are assigned normalized_keys via dedupe_key() for consistent merging
in the Neo4j graph layer.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import (
    ConceptEdge,
    ConceptMapData,
    ConceptNode,
    CostTier,
    DeadlineProfile,
    ModelTier,
)
from mindforge.domain.graph_keys import dedupe_key

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="concept_mapper",
    description="Extracts concepts and relationships to build a knowledge graph.",
    input_types=("summary", "cleaned_content"),
    output_types=("concept_map",),
    required_model_tier=ModelTier.LARGE,
    estimated_cost_tier=CostTier.MEDIUM,
)

_MAX_CONTENT_CHARS = 20_000


class ConceptMapperAgent:
    """Produces ``concept_map`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                concept_mapper as prompts,
            )  # noqa: PLC0415
        self._prompts = prompts
        self.PROMPT_VERSION = prompts.VERSION

    @property
    def name(self) -> str:
        return "concept_mapper"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        summary = context.artifact.summary
        if summary is None:
            return AgentResult(
                success=False,
                output_key="concept_map",
                error="Summary not available; ConceptMapper requires Summarizer to run first.",
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
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            log.exception("ConceptMapperAgent LLM call failed")
            return AgentResult(
                success=False,
                output_key="concept_map",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        concept_map = ConceptMapData()
        try:
            data = json.loads(result.content)

            raw_concepts = data.get("concepts", [])
            raw_relations = data.get("relations", [])

            # Build a set of valid concept keys for relation validation
            valid_keys: set[str] = set()
            nodes: list[ConceptNode] = []
            for c in raw_concepts:
                key = dedupe_key(str(c.get("key", c.get("normalized_key", ""))))
                label = str(c.get("label", key))
                definition = str(c.get("definition", c.get("description", "")))
                if not key or key == "unknown":
                    continue
                valid_keys.add(key)
                nodes.append(
                    ConceptNode(
                        key=key,
                        label=label,
                        description=definition,
                    )
                )

            edges: list[ConceptEdge] = []
            for r in raw_relations:
                src = dedupe_key(str(r.get("source_key", "")))
                tgt = dedupe_key(str(r.get("target_key", "")))
                label = str(r.get("label", "RELATES_TO"))
                if src not in valid_keys or tgt not in valid_keys:
                    continue
                edges.append(ConceptEdge(source=src, target=tgt, relation=label))

            concept_map = ConceptMapData(concepts=nodes, edges=edges)

        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            log.warning("ConceptMapperAgent failed to parse LLM response: %s", exc)

        context.artifact.concept_map = concept_map

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="concept_map",
            tokens_used=result.input_tokens + result.output_tokens,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
        )
