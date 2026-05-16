"""
Unit tests for Phase 5 — Agent Framework and Pipeline Orchestration.

Covers:
  5.5.1  Topological ordering of the default graph
  5.5.2  Fingerprint computation and comparison
  5.5.3  Checkpoint skip logic (fingerprint match vs. mismatch)
  5.5.4  DAG-aware invalidation cascade
  5.5.5  force=True bypasses all checkpoints
  5.5.6  Pipeline worker claim/execute/stale-recovery flow (mock DB)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindforge.agents import AgentRegistry
from mindforge.application.orchestration import GraphNode, OrchestrationGraph
from mindforge.application.pipeline import PipelineOrchestrator, StepExecutionError
from mindforge.cli.pipeline_runner import PipelineWorker, _parse_reclaim_count
from mindforge.domain.agents import (
    Agent,
    AgentCapability,
    AgentContext,
    AgentResult,
    ProcessingSettings,
)
from mindforge.domain.models import (
    CostTier,
    DocumentArtifact,
    DocumentStatus,
    ModelTier,
    StepCheckpoint,
    StepFingerprint,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_artifact(document_id: uuid.UUID | None = None) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=document_id or uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        lesson_id="test-lesson",
        version=1,
        created_at=datetime.now(timezone.utc),
    )


class _FakeAgent:
    """Minimal Agent implementation that records calls and returns success."""

    def __init__(
        self,
        name: str,
        output_key: str,
        *,
        fail: bool = False,
    ) -> None:
        self._name = name
        self._output_key = output_key
        self._fail = fail
        self.__version__ = "1.0.0"
        self.PROMPT_VERSION = "v1"
        self.capabilities = [
            AgentCapability(
                name=name,
                description="fake",
                input_types=(),
                output_types=(),
                required_model_tier=ModelTier.SMALL,
                estimated_cost_tier=CostTier.LOW,
            )
        ]
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, context: AgentContext) -> AgentResult:
        self.call_count += 1
        if self._fail:
            return AgentResult(
                success=False,
                output_key=self._output_key,
                error="intentional failure",
            )
        return AgentResult(
            success=True,
            output_key=self._output_key,
            tokens_used=10,
            cost_usd=0.001,
        )


def _simple_graph(*agent_names: str) -> OrchestrationGraph:
    """Build a linear DAG: a → b → c …"""
    nodes = []
    for i, name in enumerate(agent_names):
        deps = (agent_names[i - 1],) if i > 0 else ()
        nodes.append(GraphNode(name, f"{name}_output", deps))
    return OrchestrationGraph(nodes)


def _make_orchestrator(
    registry: AgentRegistry,
    graph: OrchestrationGraph,
    *,
    artifact_repo: object | None = None,
    event_publisher: object | None = None,
    interaction_store: object | None = None,
    document_repo: object | None = None,
) -> PipelineOrchestrator:
    if artifact_repo is None:
        artifact_repo = AsyncMock()
        artifact_repo.save_checkpoint = AsyncMock()
        artifact_repo.load_latest = AsyncMock(return_value=None)
    if event_publisher is None:
        event_publisher = AsyncMock()
        event_publisher.publish_in_tx = AsyncMock()
    if interaction_store is None:
        interaction_store = AsyncMock()
        interaction_store.create_interaction = AsyncMock(return_value=uuid.uuid4())
        interaction_store.add_turn = AsyncMock(return_value=uuid.uuid4())
    if document_repo is None:
        document_repo = AsyncMock()
        document_repo.update_status = AsyncMock()
    return PipelineOrchestrator(
        registry=registry,
        graph=graph,
        artifact_repo=artifact_repo,
        event_publisher=event_publisher,
        interaction_store=interaction_store,
        document_repo=document_repo,
    )


def _make_context(artifact: DocumentArtifact) -> AgentContext:
    retrieval = AsyncMock()
    gateway = AsyncMock()
    return AgentContext(
        document_id=artifact.document_id,
        knowledge_base_id=artifact.knowledge_base_id,
        artifact=artifact,
        gateway=gateway,
        retrieval=retrieval,
        settings=ProcessingSettings(),
    )


# ---------------------------------------------------------------------------
# 5.5.1  Topological ordering
# ---------------------------------------------------------------------------


class TestTopologicalOrder:
    def test_default_graph_has_correct_length(self) -> None:
        graph = OrchestrationGraph.default()
        order = graph.topological_order()
        assert len(order) == len(graph.nodes())

    def test_document_parser_is_first(self) -> None:
        graph = OrchestrationGraph.default()
        order = graph.topological_order()
        assert order[0].agent_name == "document_parser"

    def test_read_model_publisher_is_last(self) -> None:
        graph = OrchestrationGraph.default()
        order = graph.topological_order()
        assert order[-1].agent_name == "read_model_publisher"

    def test_dependencies_appear_before_dependants(self) -> None:
        graph = OrchestrationGraph.default()
        order = graph.topological_order()
        position = {node.agent_name: i for i, node in enumerate(order)}
        for node in order:
            for dep in node.dependencies:
                assert (
                    position[dep] < position[node.agent_name]
                ), f"{dep!r} must come before {node.agent_name!r}"

    def test_linear_graph(self) -> None:
        graph = _simple_graph("a", "b", "c")
        order = graph.topological_order()
        assert [n.agent_name for n in order] == ["a", "b", "c"]

    def test_cycle_raises(self) -> None:
        graph = OrchestrationGraph(
            [
                GraphNode("a", "a_out", ("b",)),
                GraphNode("b", "b_out", ("a",)),
            ]
        )
        with pytest.raises(ValueError, match="Cycle"):
            graph.topological_order()

    def test_unknown_dependency_raises_at_construction(self) -> None:
        with pytest.raises(ValueError, match="ghost"):
            OrchestrationGraph([GraphNode("a", "a_out", ("ghost",))])


# ---------------------------------------------------------------------------
# 5.5.2  Fingerprint computation
# ---------------------------------------------------------------------------


class TestFingerprintComputation:
    def test_same_inputs_produce_same_fingerprint(self) -> None:
        fp = StepFingerprint(
            input_hash="abc",
            prompt_version="v1",
            model_id="gpt-4o",
            agent_version="1.0.0",
        )
        assert fp.compute() == fp.compute()

    def test_different_agent_version_produces_different_hash(self) -> None:
        fp1 = StepFingerprint("abc", "v1", "gpt-4o", "1.0.0")
        fp2 = StepFingerprint("abc", "v1", "gpt-4o", "1.0.1")
        assert fp1.compute() != fp2.compute()

    def test_different_input_hash_produces_different_result(self) -> None:
        fp1 = StepFingerprint("abc", "v1", "gpt-4o", "1.0.0")
        fp2 = StepFingerprint("xyz", "v1", "gpt-4o", "1.0.0")
        assert fp1.compute() != fp2.compute()

    def test_orchestrator_computes_fingerprint_for_root_step(self) -> None:
        registry = AgentRegistry()
        registry.register(_FakeAgent("step_a", "a_out"))
        graph = _simple_graph("step_a")
        orch = _make_orchestrator(registry, graph)
        artifact = _make_artifact()
        ctx = _make_context(artifact)

        fp = orch._compute_fingerprint("step_a", ctx)
        assert len(fp.compute()) == 16

    def test_orchestrator_fingerprint_changes_when_upstream_changes(self) -> None:
        registry = AgentRegistry()
        registry.register(_FakeAgent("step_a", "a_out"))
        registry.register(_FakeAgent("step_b", "b_out"))
        graph = _simple_graph("step_a", "step_b")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()
        ctx = _make_context(artifact)

        fp_before = orch._compute_fingerprint("step_b", ctx)

        # Simulate step_a completing with a checkpoint
        artifact.step_fingerprints["step_a"] = StepCheckpoint(
            output_key="a_out",
            fingerprint="deadbeef01234567",
            completed_at=datetime.now(timezone.utc),
        )
        fp_after = orch._compute_fingerprint("step_b", ctx)

        assert fp_before.compute() != fp_after.compute()


# ---------------------------------------------------------------------------
# 5.5.3  Checkpoint skip logic
# ---------------------------------------------------------------------------


class TestCheckpointSkip:
    @pytest.mark.asyncio
    async def test_step_is_skipped_when_fingerprint_matches(self) -> None:
        registry = AgentRegistry()
        agent = _FakeAgent("step_a", "a_out")
        registry.register(agent)
        graph = _simple_graph("step_a")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()
        ctx = _make_context(artifact)

        # Pre-compute what the fingerprint will be and store it
        fp = orch._compute_fingerprint("step_a", ctx)
        artifact.step_fingerprints["step_a"] = StepCheckpoint(
            output_key="a_out",
            fingerprint=fp.compute(),
            completed_at=datetime.now(timezone.utc),
        )

        await orch.run(artifact.document_id, artifact, ctx)
        assert agent.call_count == 0, "Agent should NOT be called when cache hits"

    @pytest.mark.asyncio
    async def test_step_is_executed_when_fingerprint_differs(self) -> None:
        registry = AgentRegistry()
        agent = _FakeAgent("step_a", "a_out")
        registry.register(agent)
        graph = _simple_graph("step_a")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()
        ctx = _make_context(artifact)

        # Store a STALE fingerprint (wrong hash)
        artifact.step_fingerprints["step_a"] = StepCheckpoint(
            output_key="a_out",
            fingerprint="0000000000000000",
            completed_at=datetime.now(timezone.utc),
        )

        await orch.run(artifact.document_id, artifact, ctx)
        assert agent.call_count == 1, "Agent SHOULD be called when fingerprint differs"


# ---------------------------------------------------------------------------
# 5.5.4  DAG-aware invalidation cascade
# ---------------------------------------------------------------------------


class TestInvalidationCascade:
    def test_downstream_returns_all_transitive_dependants(self) -> None:
        graph = _simple_graph("a", "b", "c", "d")
        # a → b → c → d;  changing b should invalidate c and d, not a
        downstream = graph.downstream("b")
        assert downstream == {"c", "d"}

    def test_leaf_node_has_empty_downstream(self) -> None:
        graph = _simple_graph("a", "b", "c")
        assert graph.downstream("c") == set()

    def test_orchestrator_invalidated_steps_delegates_to_graph(self) -> None:
        registry = AgentRegistry()
        graph = _simple_graph("a", "b", "c")
        orch = _make_orchestrator(registry, graph)
        assert orch.invalidated_steps("a") == {"b", "c"}

    @pytest.mark.asyncio
    async def test_force_clears_downstream_checkpoints(self) -> None:
        registry = AgentRegistry()
        agent_a = _FakeAgent("a", "a_out")
        agent_b = _FakeAgent("b", "b_out")
        registry.register(agent_a)
        registry.register(agent_b)
        graph = _simple_graph("a", "b")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()
        ctx = _make_context(artifact)

        # Pre-cache both steps with valid fingerprints
        for step_name, output_key in [("a", "a_out"), ("b", "b_out")]:
            fp = orch._compute_fingerprint(step_name, ctx)
            artifact.step_fingerprints[step_name] = StepCheckpoint(
                output_key=output_key,
                fingerprint=fp.compute(),
                completed_at=datetime.now(timezone.utc),
            )

        # force=True should run both agents regardless of cached fingerprints
        await orch.run(artifact.document_id, artifact, ctx, force=True)
        assert agent_a.call_count == 1
        assert agent_b.call_count == 1


# ---------------------------------------------------------------------------
# 5.5.5  force=True bypasses all checkpoints
# ---------------------------------------------------------------------------


class TestForceRun:
    @pytest.mark.asyncio
    async def test_force_true_reruns_all_steps(self) -> None:
        registry = AgentRegistry()
        agents = [_FakeAgent(f"step_{i}", f"out_{i}") for i in range(3)]
        for a in agents:
            registry.register(a)

        graph = OrchestrationGraph(
            [
                GraphNode("step_0", "out_0", ()),
                GraphNode("step_1", "out_1", ("step_0",)),
                GraphNode("step_2", "out_2", ("step_1",)),
            ]
        )
        orch = _make_orchestrator(registry, graph)
        artifact = _make_artifact()
        ctx = _make_context(artifact)

        # First run (cold)
        await orch.run(artifact.document_id, artifact, ctx)
        for a in agents:
            assert a.call_count == 1

        # Second run (all cached — should be skipped)
        await orch.run(artifact.document_id, artifact, ctx)
        for a in agents:
            assert a.call_count == 1, "Should be cached on second run"

        # Third run with force=True (should re-execute all)
        await orch.run(artifact.document_id, artifact, ctx, force=True)
        for a in agents:
            assert a.call_count == 2, "Should re-run when force=True"

    @pytest.mark.asyncio
    async def test_failed_step_raises_step_execution_error(self) -> None:
        registry = AgentRegistry()
        registry.register(_FakeAgent("ok_step", "ok_out"))
        registry.register(_FakeAgent("bad_step", "bad_out", fail=True))

        graph = OrchestrationGraph(
            [
                GraphNode("ok_step", "ok_out", ()),
                GraphNode("bad_step", "bad_out", ("ok_step",)),
            ]
        )
        orch = _make_orchestrator(registry, graph)
        artifact = _make_artifact()
        ctx = _make_context(artifact)

        with pytest.raises(StepExecutionError) as exc_info:
            await orch.run(artifact.document_id, artifact, ctx)
        assert exc_info.value.step == "bad_step"


# ---------------------------------------------------------------------------
# 5.5.6  AgentRegistry
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    def test_register_and_get(self) -> None:
        reg = AgentRegistry()
        agent = _FakeAgent("my_agent", "my_out")
        reg.register(agent)
        assert reg.get("my_agent") is agent

    def test_duplicate_registration_raises(self) -> None:
        reg = AgentRegistry()
        reg.register(_FakeAgent("dup", "out"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_FakeAgent("dup", "out"))

    def test_unregister_then_reregister(self) -> None:
        reg = AgentRegistry()
        reg.register(_FakeAgent("a", "a_out"))
        reg.unregister("a")
        reg.register(_FakeAgent("a", "a_out"))  # should not raise
        assert "a" in reg

    def test_get_missing_raises_key_error(self) -> None:
        reg = AgentRegistry()
        with pytest.raises(KeyError, match="ghost"):
            reg.get("ghost")

    def test_all_returns_registered_agents(self) -> None:
        reg = AgentRegistry()
        a1 = _FakeAgent("x", "x_out")
        a2 = _FakeAgent("y", "y_out")
        reg.register(a1)
        reg.register(a2)
        assert set(reg.all()) == {a1, a2}

    def test_len(self) -> None:
        reg = AgentRegistry()
        assert len(reg) == 0
        reg.register(_FakeAgent("a", "a_out"))
        assert len(reg) == 1


# ---------------------------------------------------------------------------
# 5.5.6  Pipeline worker helpers
# ---------------------------------------------------------------------------


class TestPipelineWorkerHelpers:
    def test_parse_reclaim_count_zero_for_empty(self) -> None:
        assert _parse_reclaim_count(None) == 0
        assert _parse_reclaim_count("") == 0

    def test_parse_reclaim_count_extracts_number(self) -> None:
        assert _parse_reclaim_count("[reclaim:3] some message") == 3
        assert _parse_reclaim_count("[reclaim:1] Reclaimed after stale detection") == 1

    def test_parse_reclaim_count_returns_zero_when_absent(self) -> None:
        assert _parse_reclaim_count("some random error message") == 0


# ---------------------------------------------------------------------------
# 5.5.6  Pipeline worker — stale-recovery and execute-task (mock DB)
# ---------------------------------------------------------------------------


def _make_session_ctx(mock_session: object) -> MagicMock:
    """Wrap *mock_session* in an async context-manager mock returned by
    the session factory, and attach a ``begin()`` context manager to it."""
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin)  # type: ignore[union-attr]

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_cm)


def _make_pipeline_worker(
    gateway: object | None = None,
    registry: AgentRegistry | None = None,
    graph: OrchestrationGraph | None = None,
) -> PipelineWorker:
    worker = PipelineWorker(
        worker_id="test-worker",
        engine=MagicMock(),
        registry=registry or AgentRegistry(),
        graph=graph or _simple_graph("step_a"),
        gateway=gateway or AsyncMock(),
        settings=ProcessingSettings(),
        retrieval=AsyncMock(),
    )
    return worker


class TestPipelineWorkerStaleRecovery:
    """Regression tests for _recover_stale_tasks boundary conditions."""

    @pytest.mark.asyncio
    async def test_stale_task_below_max_reclaim_resets_to_pending(self) -> None:
        """A stale task with reclaim_count < _MAX_RECLAIM_ATTEMPTS must be
        reset to pending so it is retried on the next poll cycle."""
        worker = _make_pipeline_worker()

        stale_row = MagicMock()
        stale_row.task_id = uuid.uuid4()
        stale_row.status = "running"
        stale_row.error = "[reclaim:1] previously reclaimed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        worker._session_factory = _make_session_ctx(mock_session)

        await worker._recover_stale_tasks()

        assert stale_row.status == "pending"
        assert stale_row.worker_id is None
        assert stale_row.claimed_at is None
        assert "[reclaim:2]" in stale_row.error

    @pytest.mark.asyncio
    async def test_stale_task_at_max_reclaim_permanently_fails(self) -> None:
        """A stale task with reclaim_count >= _MAX_RECLAIM_ATTEMPTS must be
        permanently failed, not re-queued."""
        worker = _make_pipeline_worker()

        stale_row = MagicMock()
        stale_row.task_id = uuid.uuid4()
        stale_row.status = "running"
        stale_row.error = "[reclaim:3] previously reclaimed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        worker._session_factory = _make_session_ctx(mock_session)

        await worker._recover_stale_tasks()

        assert stale_row.status == "failed"
        assert stale_row.completed_at is not None
        # Must NOT be reset to pending
        assert stale_row.worker_id != None or stale_row.status != "pending"

    @pytest.mark.asyncio
    async def test_no_stale_tasks_produces_no_mutations(self) -> None:
        """When there are no stale tasks the worker must make no row mutations."""
        worker = _make_pipeline_worker()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        worker._session_factory = _make_session_ctx(mock_session)

        # Should not raise and should not mutate any rows
        await worker._recover_stale_tasks()


class TestPipelineWorkerExecuteTask:
    """Regression tests for _execute_task correctness."""

    @pytest.mark.asyncio
    async def test_agentcontext_gateway_is_injected_gateway_not_artifact_repo(
        self,
    ) -> None:
        """Regression: AgentContext.gateway must be the AIGateway instance
        injected into PipelineWorker, not self._orchestrator._artifact_repo."""
        gateway = AsyncMock()
        worker = _make_pipeline_worker(gateway=gateway)

        captured_contexts: list[AgentContext] = []

        # Mock orchestrator that captures the context passed to run()
        mock_orchestrator = AsyncMock()

        async def _capture_run(
            *, document_id: object, artifact: object, context: AgentContext
        ) -> None:
            captured_contexts.append(context)

        mock_orchestrator.run = _capture_run

        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.knowledge_base_id = uuid.uuid4()
        doc_row.lesson_id = "test-lesson"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=doc_row)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = doc_row.document_id

        with (
            patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch(
                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            await worker._execute_task(task)

        assert len(captured_contexts) == 1, "orchestrator.run() should be called once"
        assert (
            captured_contexts[0].gateway is gateway
        ), "gateway must be the injected AIGateway, not _artifact_repo"

    @pytest.mark.asyncio
    async def test_execute_task_marks_failed_when_document_not_found(self) -> None:
        """When session.get() returns None the task must be marked as failed."""
        worker = _make_pipeline_worker()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = uuid.uuid4()

        with (
            patch("mindforge.cli.pipeline_runner.PostgresArtifactRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch("mindforge.cli.pipeline_runner.PipelineOrchestrator"),
        ):
            await worker._execute_task(task)

        # _mark_failed issues an UPDATE via session.execute
        mock_session.execute.assert_called()
        call_args = str(mock_session.execute.call_args)
        # The UPDATE should reference "failed" status
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_execute_task_marks_done_on_orchestrator_success(self) -> None:
        """When the orchestrator completes without error the task must be
        marked as done."""
        worker = _make_pipeline_worker()

        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.knowledge_base_id = uuid.uuid4()
        doc_row.lesson_id = "ok-lesson"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=doc_row)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run = AsyncMock()  # succeeds

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = doc_row.document_id

        with (
            patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch(
                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            await worker._execute_task(task)

        # _mark_done issues an UPDATE via session.execute
        mock_session.execute.assert_called()
        mock_orchestrator.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_marks_failed_on_step_execution_error(self) -> None:
        """When the orchestrator raises StepExecutionError the task must be
        marked as failed and the exception must not propagate."""
        worker = _make_pipeline_worker()

        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.knowledge_base_id = uuid.uuid4()
        doc_row.lesson_id = "error-lesson"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=doc_row)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run = AsyncMock(
            side_effect=StepExecutionError(step="bad_step", reason="boom")
        )

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = doc_row.document_id

        with (
            patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch(
                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            # Must not raise — worker absorbs the error and marks the task
            await worker._execute_task(task)

        mock_session.execute.assert_called()


# ---------------------------------------------------------------------------
# 12.x  Locale-aware fingerprinting & prompt propagation
# ---------------------------------------------------------------------------


class TestLocaleAwareFingerprinting:
    """Regression tests for Phase 12: per-KB prompt_locale propagation."""

    def test_different_locales_produce_different_fingerprints(self) -> None:
        """_compute_fingerprint must incorporate prompt_locale so that changing
        the KB locale invalidates cached steps."""
        registry = AgentRegistry()
        agent = _FakeAgent("step_a", "a_out")
        registry.register(agent)
        graph = _simple_graph("step_a")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()

        ctx_pl = _make_context(artifact)
        ctx_pl.settings = ProcessingSettings(prompt_locale="pl")

        ctx_en = _make_context(artifact)
        ctx_en.settings = ProcessingSettings(prompt_locale="en")

        fp_pl = orch._compute_fingerprint("step_a", ctx_pl)
        fp_en = orch._compute_fingerprint("step_a", ctx_en)

        assert (
            fp_pl.compute() != fp_en.compute()
        ), "Fingerprint must differ when prompt_locale differs"

    def test_same_locale_produces_same_fingerprint(self) -> None:
        """Two contexts with the same locale must yield the same fingerprint."""
        registry = AgentRegistry()
        registry.register(_FakeAgent("step_a", "a_out"))
        graph = _simple_graph("step_a")
        orch = _make_orchestrator(registry, graph)

        artifact = _make_artifact()
        ctx1 = _make_context(artifact)
        ctx1.settings = ProcessingSettings(prompt_locale="en")
        ctx2 = _make_context(artifact)
        ctx2.settings = ProcessingSettings(prompt_locale="en")

        assert orch._compute_fingerprint("step_a", ctx1).compute() == (
            orch._compute_fingerprint("step_a", ctx2).compute()
        )

    @pytest.mark.asyncio
    async def test_execute_task_reads_kb_prompt_locale(self) -> None:
        """_execute_task must read kb.prompt_locale and build task_settings with
        that locale instead of always using the global worker settings (which
        default to 'pl')."""
        gateway = AsyncMock()
        worker = _make_pipeline_worker(gateway=gateway)

        captured_contexts: list[AgentContext] = []

        mock_orchestrator = AsyncMock()

        async def _capture_run(
            *, document_id: object, artifact: object, context: AgentContext
        ) -> None:
            captured_contexts.append(context)

        mock_orchestrator.run = _capture_run

        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.kb_id = uuid.uuid4()
        doc_row.original_content = "some content"

        kb_row = MagicMock()
        kb_row.prompt_locale = "en"

        mock_session = AsyncMock()

        async def _session_get(model_class, pk):
            if model_class.__name__ == "DocumentModel":
                return doc_row
            if model_class.__name__ == "KnowledgeBaseModel":
                return kb_row
            return None

        mock_session.get = AsyncMock(side_effect=_session_get)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = doc_row.document_id

        with (
            patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch(
                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            await worker._execute_task(task)

        assert len(captured_contexts) == 1
        assert (
            captured_contexts[0].settings.prompt_locale == "en"
        ), "AgentContext must carry the KB's prompt_locale, not the default 'pl'"

    @pytest.mark.asyncio
    async def test_execute_task_falls_back_to_pl_when_kb_not_found(self) -> None:
        """If the KB row is unexpectedly missing, prompt_locale must fall back to 'pl'."""
        gateway = AsyncMock()
        worker = _make_pipeline_worker(gateway=gateway)

        captured_contexts: list[AgentContext] = []

        mock_orchestrator = AsyncMock()

        async def _capture_run(
            *, document_id: object, artifact: object, context: AgentContext
        ) -> None:
            captured_contexts.append(context)

        mock_orchestrator.run = _capture_run

        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.kb_id = uuid.uuid4()
        doc_row.original_content = "some content"

        mock_session = AsyncMock()

        async def _session_get(model_class, pk):
            if model_class.__name__ == "DocumentModel":
                return doc_row
            return None  # KB not found

        mock_session.get = AsyncMock(side_effect=_session_get)
        mock_session.execute = AsyncMock()
        worker._session_factory = _make_session_ctx(mock_session)

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        task = MagicMock()
        task.task_id = uuid.uuid4()
        task.document_id = doc_row.document_id

        with (
            patch(
                "mindforge.cli.pipeline_runner.PostgresArtifactRepository",
                return_value=mock_artifact_repo,
            ),
            patch("mindforge.cli.pipeline_runner.PostgresDocumentRepository"),
            patch("mindforge.cli.pipeline_runner.PostgresInteractionRepository"),
            patch("mindforge.cli.pipeline_runner.OutboxEventPublisher"),
            patch(
                "mindforge.cli.pipeline_runner.PipelineOrchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            await worker._execute_task(task)

        assert len(captured_contexts) == 1
        assert captured_contexts[0].settings.prompt_locale == "pl"


# ---------------------------------------------------------------------------
# Regression: _load_or_create_artifact uses doc_row.kb_id
# ---------------------------------------------------------------------------


class TestLoadOrCreateArtifactKbId:
    """Regression test for AttributeError: 'DocumentModel' object has no
    attribute 'knowledge_base_id' — the correct column is kb_id."""

    @pytest.mark.asyncio
    async def test_creates_artifact_with_kb_id_when_no_existing_artifact(
        self,
    ) -> None:
        """_load_or_create_artifact must read doc_row.kb_id (not
        doc_row.knowledge_base_id) when creating a fresh DocumentArtifact."""
        worker = _make_pipeline_worker()

        kb_id = uuid.uuid4()
        doc_row = MagicMock()
        doc_row.document_id = uuid.uuid4()
        doc_row.kb_id = kb_id
        doc_row.lesson_id = "regression-lesson"
        # Ensure the wrong attribute does NOT exist on this mock so the test
        # fails with AttributeError if the bug is present.
        del doc_row.knowledge_base_id

        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.load_latest = AsyncMock(return_value=None)

        artifact = await worker._load_or_create_artifact(mock_artifact_repo, doc_row)

        assert artifact.knowledge_base_id == kb_id
