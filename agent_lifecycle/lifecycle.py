"""Agent lifecycle state machine."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


class AgentState(enum.Enum):
    """All possible states in an agent's lifecycle."""

    CONCEIVED = "conceived"
    BORN = "born"
    ACTIVE = "active"
    IDLE = "idle"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    DEAD = "dead"


# Valid transitions: from_state -> set of allowed to_states
_VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CONCEIVED: {AgentState.BORN, AgentState.DEAD},
    AgentState.BORN: {AgentState.ACTIVE, AgentState.DEAD},
    AgentState.ACTIVE: {AgentState.IDLE, AgentState.SUSPENDED, AgentState.RETIRED, AgentState.DEAD},
    AgentState.IDLE: {AgentState.ACTIVE, AgentState.SUSPENDED, AgentState.RETIRED, AgentState.DEAD},
    AgentState.SUSPENDED: {AgentState.ACTIVE, AgentState.IDLE, AgentState.RETIRED, AgentState.DEAD},
    AgentState.RETIRED: {AgentState.DEAD},
    AgentState.DEAD: set(),  # terminal state
}


@dataclass
class StateRecord:
    """A snapshot of an agent's state at a point in time."""

    state: AgentState
    entered_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


# Side-effect callback type: receives (agent_id, old_state, new_state, **kwargs)
SideEffect = Callable[[str, AgentState, AgentState], None]


class Lifecycle:
    """Manages an individual agent's lifecycle state machine.

    Example::

        lc = Lifecycle(agent_id="agent-42")
        lc.transition(AgentState.BORN)
        lc.transition(AgentState.ACTIVE)
        assert lc.current_state == AgentState.ACTIVE
    """

    def __init__(
        self,
        agent_id: str,
        initial_state: AgentState = AgentState.CONCEIVED,
        on_transition: Optional[SideEffect] = None,
    ) -> None:
        self.agent_id = agent_id
        self._history: list[StateRecord] = [StateRecord(state=initial_state)]
        self._on_transition = on_transition

    @property
    def current_state(self) -> AgentState:
        return self._history[-1].state

    @property
    def history(self) -> list[StateRecord]:
        return list(self._history)

    @property
    def created_at(self) -> float:
        return self._history[0].entered_at

    @property
    def state_entered_at(self) -> float:
        return self._history[-1].entered_at

    def can_transition(self, target: AgentState) -> bool:
        return target in _VALID_TRANSITIONS.get(self.current_state, set())

    def transition(
        self,
        target: AgentState,
        metadata: Optional[dict] = None,
    ) -> StateRecord:
        if not self.can_transition(target):
            raise TransitionError(
                f"Cannot transition {self.agent_id} from {self.current_state.value} "
                f"to {target.value}"
            )
        old = self.current_state
        record = StateRecord(state=target, metadata=metadata or {})
        self._history.append(record)
        if self._on_transition:
            self._on_transition(self.agent_id, old, target)
        return record

    def force_state(self, target: AgentState, metadata: Optional[dict] = None) -> StateRecord:
        """Set state without transition validation. Use with caution (e.g. recovery)."""
        old = self.current_state
        record = StateRecord(state=target, metadata=metadata or {})
        self._history.append(record)
        if self._on_transition:
            self._on_transition(self.agent_id, old, target)
        return record

    def time_in_state(self) -> float:
        return time.time() - self.state_entered_at

    def is_terminal(self) -> bool:
        return self.current_state == AgentState.DEAD

    def __repr__(self) -> str:
        return f"Lifecycle(agent_id={self.agent_id!r}, state={self.current_state.value})"


# Import here to avoid circular imports at module level — TransitionError lives in transition.py
from agent_lifecycle.transition import TransitionError  # noqa: E402
