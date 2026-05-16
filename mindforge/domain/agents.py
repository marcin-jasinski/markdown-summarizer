"""
Domain layer — agent protocols and context structures.

Defines the abstract Agent protocol that all AI agent implementations
must satisfy, plus the shared context/result dataclasses.

Pure Python only.  Zero I/O, zero framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from mindforge.domain.models import (
    CostTier,
    DocumentArtifact,
    ModelTier,
)

if TYPE_CHECKING:
    from mindforge.domain.ports import AIGateway, RetrievalPort


# ---------------------------------------------------------------------------
# Processing settings (domain-level subset of AppSettings)
# ---------------------------------------------------------------------------


@dataclass
class ProcessingSettings:
    """Chunking configuration, feature flags, and model-tier mappings.

    Constructed in infrastructure layer from ``AppSettings`` and injected
    into agents via ``AgentContext``.
    """

    chunk_max_tokens: int = 2048
    chunk_min_tokens: int = 256
    chunk_overlap_tokens: int = 64

    # Feature flags
    enable_graph: bool = True
    enable_image_analysis: bool = True
    enable_article_fetch: bool = True
    enable_semantic_cache: bool = True

    # Logical-name to LiteLLM-string mapping, e.g. {"small": "gpt-4o-mini", ...}
    model_tier_map: dict[str, str] = field(default_factory=dict)

    # Prompt locale — controls which prompt language variant is loaded
    prompt_locale: str = "pl"

    def model_for_tier(self, tier: ModelTier) -> str:
        """Return the LiteLLM model string for a given model tier."""
        return self.model_tier_map.get(tier.value.lower(), "")


# ---------------------------------------------------------------------------
# Agent capability declaration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentCapability:
    name: str
    description: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    required_model_tier: ModelTier
    estimated_cost_tier: CostTier


# ---------------------------------------------------------------------------
# Agent context (passed to every agent execution)
# ---------------------------------------------------------------------------


@dataclass
class AgentContext:
    document_id: UUID
    knowledge_base_id: UUID
    artifact: DocumentArtifact
    gateway: AIGateway
    retrieval: RetrievalPort
    settings: ProcessingSettings
    tracer: Any = None  # TracerPort — typed as Any to avoid forward-ref issues
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent result
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    success: bool
    output_key: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def failed(self) -> bool:
        return not self.success


# ---------------------------------------------------------------------------
# Agent protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Agent(Protocol):
    """Contract that every AI agent implementation must satisfy."""

    @property
    def name(self) -> str:
        """Unique agent identifier used in step fingerprints and logs."""
        ...

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        """Declared capabilities of this agent."""
        ...

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the agent, mutate ``context.artifact`` with results,
        and return an ``AgentResult``."""
        ...
