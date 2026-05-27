"""Heartbeat monitor — tracks agent liveness via periodic check-ins."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    DEAD = "dead"


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat thresholds."""

    interval_seconds: float = 30.0
    missed_threshold: int = 3  # after this many missed → UNRESPONSIVE
    degraded_factor: float = 2.0  # interval × factor → DEGRADED


@dataclass
class HeartbeatRecord:
    """Tracks heartbeat state for a single agent."""

    agent_id: str
    last_heartbeat: float = 0.0
    missed_count: int = 0
    config: HeartbeatConfig = field(default_factory=HeartbeatConfig)

    @property
    def status(self) -> HealthStatus:
        if self.last_heartbeat == 0.0:
            return HealthStatus.UNRESPONSIVE
        elapsed = time.time() - self.last_heartbeat
        degraded_cutoff = self.config.interval_seconds * self.config.degraded_factor
        missed_cutoff = self.config.interval_seconds * self.config.missed_threshold
        if elapsed > missed_cutoff:
            return HealthStatus.UNRESPONSIVE
        if elapsed > degraded_cutoff:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    @property
    def elapsed(self) -> float:
        if self.last_heartbeat == 0.0:
            return float("inf")
        return time.time() - self.last_heartbeat


# Callback when status changes
StatusChangeCallback = Callable[[str, HealthStatus, HealthStatus], None]


class HeartbeatMonitor:
    """Monitors agent liveness via heartbeats.

    Example::

        monitor = HeartbeatMonitor()
        monitor.register("agent-42")
        monitor.beat("agent-42")
        assert monitor.check("agent-42") == HealthStatus.HEALTHY
    """

    def __init__(
        self,
        default_config: Optional[HeartbeatConfig] = None,
        on_status_change: Optional[StatusChangeCallback] = None,
    ) -> None:
        self._records: dict[str, HeartbeatRecord] = {}
        self._default_config = default_config or HeartbeatConfig()
        self._on_status_change = on_status_change
        self._last_status: dict[str, HealthStatus] = {}

    def register(self, agent_id: str, config: Optional[HeartbeatConfig] = None) -> HeartbeatRecord:
        record = HeartbeatRecord(
            agent_id=agent_id,
            config=config or self._default_config,
        )
        self._records[agent_id] = record
        self._last_status[agent_id] = HealthStatus.UNRESPONSIVE
        return record

    def deregister(self, agent_id: str) -> None:
        self._records.pop(agent_id, None)
        self._last_status.pop(agent_id, None)

    def beat(self, agent_id: str) -> None:
        """Record a heartbeat for the given agent."""
        if agent_id not in self._records:
            raise KeyError(f"Agent {agent_id!r} not registered with heartbeat monitor")
        rec = self._records[agent_id]
        rec.last_heartbeat = time.time()
        rec.missed_count = 0
        self._check_status_change(agent_id)

    def check(self, agent_id: str) -> HealthStatus:
        if agent_id not in self._records:
            raise KeyError(f"Agent {agent_id!r} not registered with heartbeat monitor")
        return self._records[agent_id].status

    def check_all(self) -> dict[str, HealthStatus]:
        result = {}
        for aid in self._records:
            result[aid] = self._records[aid].status
        return result

    def unresponsive_agents(self) -> list[str]:
        return [aid for aid, rec in self._records.items() if rec.status == HealthStatus.UNRESPONSIVE]

    def mark_dead(self, agent_id: str) -> None:
        """Permanently mark an agent as dead (removes from monitoring)."""
        self._records.pop(agent_id, None)
        self._last_status.pop(agent_id, None)

    def _check_status_change(self, agent_id: str) -> None:
        new_status = self._records[agent_id].status
        old_status = self._last_status.get(agent_id, HealthStatus.UNRESPONSIVE)
        self._last_status[agent_id] = new_status
        if new_status != old_status and self._on_status_change:
            self._on_status_change(agent_id, old_status, new_status)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._records

    def __len__(self) -> int:
        return len(self._records)
