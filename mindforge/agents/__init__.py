"""
Agent registry — Open/Closed registration of AI agent implementations.

Adding a new agent means registering it here (or in a composition root)
without modifying the orchestrator or the registry itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mindforge.domain.agents import Agent


class AgentRegistry:
    """Thread-safe in-process registry for :class:`~mindforge.domain.agents.Agent`
    implementations.

    Usage::

        registry = AgentRegistry()
        registry.register(PreprocessorAgent())
        agent = registry.get("preprocessor")
    """

    def __init__(self) -> None:
        self._agents: dict[str, "Agent"] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, agent: "Agent") -> None:
        """Register *agent* under its :attr:`~mindforge.domain.agents.Agent.name`.

        Raises :exc:`ValueError` if an agent with the same name is already
        registered.  Re-registration must be explicit — call
        :meth:`unregister` first.
        """
        if agent.name in self._agents:
            raise ValueError(
                f"Agent {agent.name!r} is already registered. "
                "Call unregister() before replacing it."
            )
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        """Remove the agent registered under *name* (no-op if absent)."""
        self._agents.pop(name, None)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, name: str) -> "Agent":
        """Return the agent registered under *name*.

        Raises :exc:`KeyError` if no agent with that name is registered.
        """
        try:
            return self._agents[name]
        except KeyError:
            raise KeyError(
                f"No agent registered with name {name!r}. "
                f"Available: {sorted(self._agents)}"
            )

    def all(self) -> list["Agent"]:
        """Return all registered agents in insertion order."""
        return list(self._agents.values())

    def names(self) -> list[str]:
        """Return sorted list of registered agent names."""
        return sorted(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)

    def __repr__(self) -> str:
        return f"AgentRegistry(agents={self.names()})"
