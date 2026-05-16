"""
Application layer — pipeline orchestration graph.

Defines the DAG of agent steps and provides topological ordering.
No I/O; pure graph logic only.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Graph node
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphNode:
    """A single step in the pipeline DAG.

    Attributes:
        agent_name:   Corresponds to :attr:`~mindforge.domain.agents.Agent.name`.
        output_key:   The field on :class:`~mindforge.domain.models.DocumentArtifact`
                      that this step writes (used for fingerprint + skip logic).
        dependencies: Names of upstream :class:`GraphNode` steps whose outputs
                      this step requires as inputs.
    """

    agent_name: str
    output_key: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Orchestration graph
# ---------------------------------------------------------------------------


class OrchestrationGraph:
    """Directed acyclic graph of pipeline :class:`GraphNode` steps.

    Usage::

        graph = OrchestrationGraph.default()
        for step in graph.topological_order():
            ...
    """

    def __init__(self, nodes: list[GraphNode]) -> None:
        self._nodes: dict[str, GraphNode] = {n.agent_name: n for n in nodes}
        self._validate()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> OrchestrationGraph:
        """Return the standard MindForge document-processing pipeline DAG.

        Architecture Section 9.4::

            document_parser
                └─ relevance_guard
                       ├─ image_analyzer  (parallel)
                       └─ preprocessor    (parallel)
                              └─ article_fetcher
                                     └─ summarizer
                                            ├─ flashcard_generator  (parallel)
                                            └─ concept_mapper        (parallel)
                                                   └─ validation
                                                          └─ graph_indexer
                                                                 └─ read_model_publisher
        """
        return cls(
            [
                GraphNode("document_parser", "parsed_content", ()),
                GraphNode("relevance_guard", "validation_result", ("document_parser",)),
                GraphNode(
                    "image_analyzer",
                    "image_descriptions",
                    ("relevance_guard",),
                ),
                GraphNode(
                    "preprocessor",
                    "cleaned_content",
                    ("relevance_guard",),
                ),
                GraphNode(
                    "article_fetcher",
                    "fetched_articles",
                    ("preprocessor",),
                ),
                GraphNode(
                    "summarizer",
                    "summary",
                    ("preprocessor", "image_analyzer", "article_fetcher"),
                ),
                GraphNode(
                    "flashcard_generator",
                    "flashcards",
                    ("summarizer",),
                ),
                GraphNode(
                    "concept_mapper",
                    "concept_map",
                    ("summarizer",),
                ),
                GraphNode(
                    "validation",
                    "final_validation",
                    ("flashcard_generator", "concept_mapper"),
                ),
                GraphNode(
                    "graph_indexer",
                    "graph_indexed",
                    ("validation",),
                ),
                GraphNode(
                    "read_model_publisher",
                    "read_model_published",
                    ("graph_indexer",),
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def topological_order(self) -> list[GraphNode]:
        """Return nodes in a valid topological order using Kahn's algorithm.

        Raises :exc:`ValueError` if the graph contains a cycle.
        """
        # Build in-degree counts and adjacency list
        in_degree: dict[str, int] = {name: 0 for name in self._nodes}
        successors: dict[str, list[str]] = {name: [] for name in self._nodes}

        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    raise ValueError(
                        f"Node {node.agent_name!r} depends on unknown step {dep!r}"
                    )
                in_degree[node.agent_name] += 1
                successors[dep].append(node.agent_name)

        queue: deque[str] = deque(name for name, deg in in_degree.items() if deg == 0)
        result: list[GraphNode] = []

        while queue:
            name = queue.popleft()
            result.append(self._nodes[name])
            for succ in successors[name]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(result) != len(self._nodes):
            processed = {n.agent_name for n in result}
            cycle_nodes = sorted(set(self._nodes) - processed)
            raise ValueError(
                f"Cycle detected in orchestration graph. "
                f"Nodes involved: {cycle_nodes}"
            )

        return result

    def dependencies(self, step_name: str) -> list[str]:
        """Return the direct dependency names for *step_name*."""
        node = self._nodes.get(step_name)
        if node is None:
            raise KeyError(f"Unknown step: {step_name!r}")
        return list(node.dependencies)

    def downstream(self, step_name: str) -> set[str]:
        """Return all transitive downstream dependent step names (excluding
        *step_name* itself).

        Used by :meth:`~PipelineOrchestrator.invalidated_steps` to determine
        which cached outputs to invalidate when an upstream step re-runs.
        """
        if step_name not in self._nodes:
            raise KeyError(f"Unknown step: {step_name!r}")

        # Build reverse adjacency: step → its direct dependants
        dependants: dict[str, list[str]] = {name: [] for name in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                dependants[dep].append(node.agent_name)

        # BFS from step_name
        visited: set[str] = set()
        queue: deque[str] = deque(dependants[step_name])
        while queue:
            name = queue.popleft()
            if name in visited:
                continue
            visited.add(name)
            queue.extend(dependants[name])
        return visited

    def node(self, step_name: str) -> GraphNode:
        """Return the :class:`GraphNode` for *step_name*."""
        try:
            return self._nodes[step_name]
        except KeyError:
            raise KeyError(f"Unknown step: {step_name!r}")

    def nodes(self) -> list[GraphNode]:
        """Return all nodes (unordered)."""
        return list(self._nodes.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Eagerly validate that all declared dependencies are present."""
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    raise ValueError(
                        f"Node {node.agent_name!r} declares dependency "
                        f"{dep!r} which is not registered in the graph."
                    )
