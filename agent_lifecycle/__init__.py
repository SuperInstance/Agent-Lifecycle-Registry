"""
agent-lifecycle — Agent lifecycle management library.

Track agent birth, state transitions, health, and death.
"""

from agent_lifecycle.lifecycle import AgentState, Lifecycle
from agent_lifecycle.registry import AgentRegistry
from agent_lifecycle.transition import StateTransition, TransitionError
from agent_lifecycle.heartbeat import HeartbeatMonitor, HeartbeatConfig, HealthStatus
from agent_lifecycle.audit import AuditLog, AuditEntry, AuditEventType

__version__ = "0.1.0"
__all__ = [
    "AgentState",
    "Lifecycle",
    "AgentRegistry",
    "StateTransition",
    "TransitionError",
    "HeartbeatMonitor",
    "HeartbeatConfig",
    "HealthStatus",
    "AuditLog",
    "AuditEntry",
    "AuditEventType",
]
