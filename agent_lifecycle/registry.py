"""Agent registry — registration, lookup, health monitoring."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from agent_lifecycle.lifecycle import AgentState, Lifecycle


@dataclass
class AgentRecord:
    """Stored information about a registered agent."""

    agent_id: str
    lifecycle: Lifecycle
    metadata: dict = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    tags: set[str] = field(default_factory=set)


class AgentRegistry:
    """Central registry for tracking all known agents.

    Example::

        reg = AgentRegistry()
        reg.register("agent-42", metadata={"role": "worker"})
        reg.transition("agent-42", AgentState.ACTIVE)
        alive = reg.list_agents(states={AgentState.ACTIVE, AgentState.IDLE})
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}

    # ── Registration ──────────────────────────────────────────────

    def register(
        self,
        agent_id: str,
        metadata: Optional[dict] = None,
        tags: Optional[set[str]] = None,
        initial_state: AgentState = AgentState.CONCEIVED,
    ) -> AgentRecord:
        if agent_id in self._agents:
            raise ValueError(f"Agent {agent_id!r} is already registered")
        lc = Lifecycle(agent_id=agent_id, initial_state=initial_state)
        record = AgentRecord(
            agent_id=agent_id,
            lifecycle=lc,
            metadata=metadata or {},
            tags=tags or set(),
        )
        self._agents[agent_id] = record
        return record

    def deregister(self, agent_id: str) -> AgentRecord:
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id!r} not found")
        return self._agents.pop(agent_id)

    def get(self, agent_id: str) -> AgentRecord:
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id!r} not found")
        return self._agents[agent_id]

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def __len__(self) -> int:
        return len(self._agents)

    # ── Queries ───────────────────────────────────────────────────

    def list_agents(
        self,
        states: Optional[set[AgentState]] = None,
        tags: Optional[set[str]] = None,
    ) -> list[AgentRecord]:
        results = list(self._agents.values())
        if states is not None:
            results = [r for r in results if r.lifecycle.current_state in states]
        if tags is not None:
            results = [r for r in results if r.tags & tags]
        return results

    def list_active(self) -> list[AgentRecord]:
        """Agents in ACTIVE or IDLE state."""
        return self.list_agents(states={AgentState.ACTIVE, AgentState.IDLE})

    def list_alive(self) -> list[AgentRecord]:
        """All agents that are not DEAD."""
        return [r for r in self._agents.values() if not r.lifecycle.is_terminal()]

    # ── Transitions ───────────────────────────────────────────────

    def transition(self, agent_id: str, target: AgentState, metadata: Optional[dict] = None) -> None:
        record = self.get(agent_id)
        record.lifecycle.transition(target, metadata=metadata)
        record.last_seen = time.time()

    # ── Health ────────────────────────────────────────────────────

    def touch(self, agent_id: str) -> None:
        """Update last_seen timestamp without changing state."""
        record = self.get(agent_id)
        record.last_seen = time.time()

    def unhealthy(self, max_idle_seconds: float = 300.0) -> list[AgentRecord]:
        """Return agents whose last_seen exceeds the threshold but aren't terminal."""
        cutoff = time.time() - max_idle_seconds
        return [
            r for r in self._agents.values()
            if not r.lifecycle.is_terminal() and r.last_seen < cutoff
        ]

    def summary(self) -> dict[AgentState, int]:
        """Count of agents per state."""
        counts: dict[AgentState, int] = {s: 0 for s in AgentState}
        for record in self._agents.values():
            counts[record.lifecycle.current_state] += 1
        return counts
