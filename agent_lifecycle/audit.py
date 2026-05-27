"""Audit log — records all lifecycle events for compliance and debugging."""

from __future__ import annotations

import enum
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class AuditEventType(enum.Enum):
    """Types of auditable events."""

    REGISTERED = "registered"
    DEREGISTERED = "deregistered"
    TRANSITION = "transition"
    HEARTBEAT = "heartbeat"
    HEALTH_CHANGE = "health_change"
    FORCE_STATE = "force_state"
    ALERT = "alert"
    ERROR = "error"


@dataclass
class AuditEntry:
    """A single audit log entry."""

    timestamp: float = field(default_factory=time.time)
    event_type: AuditEventType = AuditEventType.ALERT
    agent_id: str = ""
    message: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AuditEntry:
        return cls(
            timestamp=data["timestamp"],
            event_type=AuditEventType(data["event_type"]),
            agent_id=data["agent_id"],
            message=data["message"],
            details=data.get("details", {}),
        )


class AuditLog:
    """Append-only audit log for lifecycle events.

    Supports in-memory storage and optional JSONL file persistence.

    Example::

        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="agent-42",
                   message="Agent registered")
        log.record(AuditEventType.TRANSITION, agent_id="agent-42",
                   message="born → active",
                   details={"from": "born", "to": "active"})
        entries = log.query(agent_id="agent-42")
    """

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self._entries: list[AuditEntry] = []
        self._path = Path(path) if path else None

    def record(
        self,
        event_type: AuditEventType,
        agent_id: str = "",
        message: str = "",
        details: Optional[dict] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            event_type=event_type,
            agent_id=agent_id,
            message=message,
            details=details or {},
        )
        self._entries.append(entry)
        if self._path:
            self._append_to_file(entry)
        return entry

    def query(
        self,
        agent_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> list[AuditEntry]:
        results = self._entries
        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]
        if event_type is not None:
            results = [e for e in results if e.event_type == event_type]
        if since is not None:
            results = [e for e in results if e.timestamp >= since]
        if until is not None:
            results = [e for e in results if e.timestamp <= until]
        if limit is not None:
            results = results[-limit:]
        return results

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def _append_to_file(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), default=str)
        with self._path.open("a") as f:  # type: ignore[union-attr]
            f.write(line + "\n")

    @classmethod
    def from_file(cls, path: Path | str) -> AuditLog:
        """Load an audit log from a JSONL file."""
        log = cls(path=path)
        p = Path(path)
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    entry = AuditEntry.from_dict(json.loads(line))
                    log._entries.append(entry)
        return log

    def clear(self) -> int:
        """Clear in-memory entries. Returns count of cleared entries."""
        count = len(self._entries)
        self._entries.clear()
        return count
