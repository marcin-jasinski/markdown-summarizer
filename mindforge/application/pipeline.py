"""
Application layer — pipeline orchestrator.

Executes agent steps in topological order with:
- Per-step fingerprint computation and checkpoint skip
- Transactional artifact flush + outbox event after each LLM-producing step
- DAG-aware invalidation when a step is forced to re-run
- Interaction turn recording for audit trail

No database drivers, no LLM SDK imports — all I/O through injected ports.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from mindforge.application.orchestration import OrchestrationGraph
from mindforge.domain.agents import AgentContext, AgentResult
from mindforge.domain.events import (
    PipelineStepCompleted,
    ProcessingCompleted,
    ProcessingFailed,
)
from mindforge.domain.models import (
    DocumentArtifact,
    DocumentStatus,
    StepCheckpoint,
    StepFingerprint,
)
from mindforge.domain.ports import (
    ArtifactRepository,
    DocumentRepository,
    EventPublisher,
    InteractionStore,
)

if TYPE_CHECKING:
    from mindforge.agents import AgentRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class PipelineOrchestrator:
    """Orchestrates the execution of registered agents over a document artifact.

    Constructor parameters are injected at composition-root time — no
    module-level singletons or import-time I/O.

    Args:
        registry:       Registry containing all concrete agent implementations.
        graph:          DAG describing step order and dependencies.
        artifact_repo:  Port for persisting/loading :class:`DocumentArtifact`
                        checkpoints.
        event_publisher: Port for writing outbox events within transactions.
        interaction_store: Port for recording per-step audit turns.
        document_repo:  Port for updating document processing status.
    """

    def __init__(
        self,
        registry: "AgentRegistry",
        graph: OrchestrationGraph,
        artifact_repo: ArtifactRepository,
        event_publisher: EventPublisher,
        interaction_store: InteractionStore,
        document_repo: DocumentRepository,
    ) -> None:
        self._registry = registry
        self._graph = graph
        self._artifact_repo = artifact_repo
        self._event_publisher = event_publisher
        self._interaction_store = interaction_store
        self._document_repo = document_repo

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        document_id: UUID,
        artifact: DocumentArtifact,
        context: AgentContext,
        *,
        force: bool = False,
    ) -> DocumentArtifact:
        """Execute the full pipeline for *document_id*.

        Args:
            document_id: The document being processed.
            artifact:    The :class:`DocumentArtifact` to update.
            context:     Shared :class:`~mindforge.domain.agents.AgentContext`
                         (gateway, retrieval, settings, …).
            force:       When ``True``, bypass all cached checkpoints and
                         re-execute every step.

        Returns:
            The final :class:`DocumentArtifact` after all steps complete.

        The method updates ``context.artifact`` in-place and also persists
        each step checkpoint transactionally as it completes.
        """
        interaction_id = await self._interaction_store.create_interaction(
            interaction_type="pipeline",
            kb_id=context.knowledge_base_id,
        )

        await self._document_repo.update_status(document_id, DocumentStatus.PROCESSING)

        steps = self._graph.topological_order()

        try:
            for node in steps:
                if node.agent_name not in self._registry:
                    logger.debug(
                        "Skipping unregistered step %r (agent not registered)",
                        node.agent_name,
                    )
                    continue

                agent = self._registry.get(node.agent_name)

                # Build the fingerprint for this step
                fingerprint = self._compute_fingerprint(node.agent_name, context)

                # Checkpoint skip check
                if not force and artifact.is_step_cached(node.agent_name, fingerprint):
                    logger.debug(
                        "Step %r: cache hit (fingerprint=%s) — skipping",
                        node.agent_name,
                        fingerprint.compute(),
                    )
                    continue

                # If force=True, clear downstream caches to prevent stale data
                if force:
                    for downstream in self._graph.downstream(node.agent_name):
                        artifact.step_fingerprints.pop(downstream, None)

                # Execute
                logger.info("Step %r: executing", node.agent_name)
                context.artifact = artifact
                start_ms = time.monotonic() * 1000
                result: AgentResult = await agent.execute(context)
                elapsed_ms = time.monotonic() * 1000 - start_ms

                if not result.success:
                    logger.error("Step %r failed: %s", node.agent_name, result.error)
                    await self._record_turn(
                        interaction_id,
                        node.agent_name,
                        result,
                        elapsed_ms,
                        success=False,
                    )
                    raise StepExecutionError(
                        step=node.agent_name, reason=result.error or "unknown"
                    )

                # Store checkpoint
                checkpoint = StepCheckpoint(
                    output_key=node.output_key,
                    fingerprint=fingerprint.compute(),
                    completed_at=datetime.now(timezone.utc),
                )
                artifact.step_fingerprints[node.agent_name] = checkpoint
                artifact.completed_step = node.agent_name

                # Transactional flush: artifact checkpoint + outbox event
                await self._flush(artifact, document_id, node.agent_name, result)

                # Audit turn
                await self._record_turn(
                    interaction_id, node.agent_name, result, elapsed_ms, success=True
                )

                logger.info(
                    "Step %r: done in %.0fms (tokens=%d, cost=$%.6f)",
                    node.agent_name,
                    elapsed_ms,
                    result.tokens_used,
                    result.cost_usd,
                )

        except StepExecutionError as exc:
            await self._document_repo.update_status(document_id, DocumentStatus.FAILED)
            await self._event_publisher.publish_in_tx(
                ProcessingFailed(
                    document_id=document_id,
                    knowledge_base_id=context.knowledge_base_id,
                    reason=exc.reason,
                    timestamp=datetime.now(timezone.utc),
                ),
                None,
            )
            raise

        except Exception as exc:
            await self._document_repo.update_status(document_id, DocumentStatus.FAILED)
            await self._event_publisher.publish_in_tx(
                ProcessingFailed(
                    document_id=document_id,
                    knowledge_base_id=context.knowledge_base_id,
                    reason=str(exc),
                    timestamp=datetime.now(timezone.utc),
                ),
                None,
            )
            raise StepExecutionError(
                step=artifact.completed_step or "unknown", reason=str(exc)
            ) from exc

        # All steps succeeded
        await self._document_repo.update_status(document_id, DocumentStatus.DONE)
        await self._event_publisher.publish_in_tx(
            ProcessingCompleted(
                document_id=document_id,
                knowledge_base_id=context.knowledge_base_id,
                lesson_id=artifact.lesson_id,
                timestamp=datetime.now(timezone.utc),
            ),
            None,
        )
        logger.info("Pipeline complete for document %s", document_id)
        return artifact

    # ------------------------------------------------------------------
    # Fingerprint computation
    # ------------------------------------------------------------------

    def _compute_fingerprint(
        self, step_name: str, context: AgentContext
    ) -> StepFingerprint:
        """Compute the :class:`~mindforge.domain.models.StepFingerprint` for
        *step_name* based on the current artifact state and agent version.

        The input hash is derived from the output fields of all upstream
        dependency steps, ensuring that any upstream change propagates a new
        fingerprint to all downstream steps.
        """
        agent = self._registry.get(step_name)
        agent_version = getattr(agent, "__version__", "0.0.0")

        # Hash the upstream outputs as the "input" for this step
        dep_names = self._graph.dependencies(step_name)
        input_parts: list[str] = []
        for dep in dep_names:
            checkpoint = context.artifact.step_fingerprints.get(dep)
            if checkpoint is not None:
                input_parts.append(checkpoint.fingerprint)
            else:
                # Dep not yet computed — use document content hash as base
                input_parts.append(str(context.document_id))
        input_hash = hashlib.sha256("|".join(input_parts).encode()).hexdigest()[:16]

        # Use the agent's model tier to derive the model_id for the fingerprint
        model_id: str = ""
        capabilities = getattr(agent, "capabilities", None)
        if capabilities:
            for cap in (
                capabilities if isinstance(capabilities, list) else [capabilities]
            ):
                tier = getattr(cap, "required_model_tier", None)
                if tier is not None:
                    model_id = context.settings.model_for_tier(tier)
                    break

        # Encode the actual KB locale into the prompt version so that a locale
        # change automatically invalidates all pipeline checkpoints for the
        # affected document (ADR-18).  The agent's PROMPT_VERSION carries a
        # base version string that may already include the default locale suffix
        # (e.g. "1.0.0+pl").  We replace the suffix with the runtime locale
        # so that "1.0.0+pl" becomes "1.0.0+en" when the KB uses English prompts.
        base_prompt_version = getattr(agent, "PROMPT_VERSION", "0")
        if "+" in base_prompt_version:
            base_prompt_version = base_prompt_version.rsplit("+", 1)[0]
        prompt_version = f"{base_prompt_version}+{context.settings.prompt_locale}"

        return StepFingerprint(
            input_hash=input_hash,
            prompt_version=prompt_version,
            model_id=model_id,
            agent_version=agent_version,
        )

    # ------------------------------------------------------------------
    # DAG invalidation
    # ------------------------------------------------------------------

    def invalidated_steps(self, changed_step: str) -> set[str]:
        """Return all transitive downstream steps that must be invalidated
        when *changed_step* is re-run.

        Delegates to :meth:`OrchestrationGraph.downstream`.
        """
        return self._graph.downstream(changed_step)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _flush(
        self,
        artifact: DocumentArtifact,
        document_id: UUID,
        step_name: str,
        result: AgentResult,
    ) -> None:
        """Persist the artifact checkpoint and publish a step-completed event.

        Both writes happen in the same logical unit so that partial failures
        do not leave the system in an inconsistent state.
        """
        await self._artifact_repo.save_checkpoint(artifact)
        checkpoint = artifact.step_fingerprints.get(step_name)
        fingerprint_val = checkpoint.fingerprint if checkpoint else ""
        await self._event_publisher.publish_in_tx(
            PipelineStepCompleted(
                document_id=document_id,
                knowledge_base_id=artifact.knowledge_base_id,
                step_name=step_name,
                fingerprint=fingerprint_val,
                timestamp=datetime.now(timezone.utc),
            ),
            None,
        )

    async def _record_turn(
        self,
        interaction_id: UUID,
        step_name: str,
        result: AgentResult,
        elapsed_ms: float,
        *,
        success: bool,
    ) -> None:
        output: dict[str, Any] = {
            "success": success,
            "output_key": result.output_key,
            "tokens_used": result.tokens_used,
        }
        if result.error:
            output["error"] = result.error
        await self._interaction_store.add_turn(
            interaction_id,
            actor_type="agent",
            actor_id=step_name,
            action="execute",
            output_data=output,
            duration_ms=int(elapsed_ms),
            cost=result.cost_usd if result.cost_usd else None,
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StepExecutionError(RuntimeError):
    """Raised when a pipeline step fails (agent returns ``success=False``)."""

    def __init__(self, step: str, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"Pipeline step {step!r} failed: {reason}")
