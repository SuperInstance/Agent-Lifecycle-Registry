"""State transition logic with guards, side effects, and rollback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from agent_lifecycle.lifecycle import AgentState


class TransitionError(Exception):
    """Raised when a state transition is invalid or blocked by a guard."""


# Guard function: returns True if the transition is allowed
Guard = Callable[[str, AgentState, AgentState], bool]
# Side-effect callback
SideEffect = Callable[[str, AgentState, AgentState], None]
# Rollback callback — called when a transition needs to be reverted
RollbackFn = Callable[[str, AgentState, AgentState], None]


@dataclass
class TransitionResult:
    """Outcome of a transition attempt."""

    success: bool
    from_state: AgentState
    to_state: AgentState
    error: Optional[str] = None
    rolled_back: bool = False


@dataclass
class TransitionRule:
    """A rule governing a specific state transition.

    Combines optional guards (preconditions), side effects (post-actions),
    and rollback handlers for recovery.
    """

    from_state: AgentState
    to_state: AgentState
    guards: list[Guard] = field(default_factory=list)
    side_effects: list[SideEffect] = field(default_factory=list)
    rollback_fns: list[RollbackFn] = field(default_factory=list)

    def check_guards(self, agent_id: str) -> Optional[str]:
        for i, guard in enumerate(self.guards):
            if not guard(agent_id, self.from_state, self.to_state):
                return f"Guard {i} blocked transition {self.from_state.value}→{self.to_state.value}"
        return None


class StateTransition:
    """Manages transition rules, guards, side effects, and rollback.

    Example::

        stm = StateTransition()

        def must_be_registered(agent_id, from_s, to_s):
            return agent_id in registry

        stm.add_rule(AgentState.BORN, AgentState.ACTIVE,
                      guards=[must_be_registered])

        result = stm.execute("agent-42", AgentState.BORN, AgentState.ACTIVE)
        assert result.success
    """

    def __init__(self) -> None:
        self._rules: dict[tuple[AgentState, AgentState], TransitionRule] = {}

    def add_rule(
        self,
        from_state: AgentState,
        to_state: AgentState,
        guards: Optional[list[Guard]] = None,
        side_effects: Optional[list[SideEffect]] = None,
        rollback_fns: Optional[list[RollbackFn]] = None,
    ) -> TransitionRule:
        key = (from_state, to_state)
        rule = TransitionRule(
            from_state=from_state,
            to_state=to_state,
            guards=guards or [],
            side_effects=side_effects or [],
            rollback_fns=rollback_fns or [],
        )
        self._rules[key] = rule
        return rule

    def get_rule(self, from_state: AgentState, to_state: AgentState) -> Optional[TransitionRule]:
        return self._rules.get((from_state, to_state))

    def check(self, agent_id: str, from_state: AgentState, to_state: AgentState) -> Optional[str]:
        """Return None if transition is allowed, or an error message."""
        rule = self.get_rule(from_state, to_state)
        if rule is None:
            return None  # No specific rule → no guard blocking
        return rule.check_guards(agent_id)

    def execute(
        self,
        agent_id: str,
        from_state: AgentState,
        to_state: AgentState,
        on_failure: Optional[Callable[[str], None]] = None,
    ) -> TransitionResult:
        """Execute a transition: check guards, run side effects, rollback on error."""
        block_reason = self.check(agent_id, from_state, to_state)
        if block_reason:
            result = TransitionResult(
                success=False, from_state=from_state, to_state=to_state, error=block_reason
            )
            if on_failure:
                on_failure(result.error or "unknown error")
            return result

        rule = self.get_rule(from_state, to_state)

        # Run side effects; if any raises, rollback
        if rule:
            effects_run: list[int] = []
            try:
                for i, effect in enumerate(rule.side_effects):
                    effect(agent_id, from_state, to_state)
                    effects_run.append(i)
            except Exception as exc:
                # Rollback in reverse order
                if rule.rollback_fns:
                    for rb in reversed(rule.rollback_fns):
                        try:
                            rb(agent_id, to_state, from_state)
                        except Exception:
                            pass  # best-effort rollback
                result = TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error=f"Side effect failed: {exc}",
                    rolled_back=True,
                )
                if on_failure:
                    on_failure(result.error or "unknown error")
                return result

        return TransitionResult(success=True, from_state=from_state, to_state=to_state)

    @property
    def rules(self) -> list[TransitionRule]:
        return list(self._rules.values())
