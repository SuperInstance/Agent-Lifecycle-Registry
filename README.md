# Agent Lifecycle Registry

A Python library for tracking agent lifecycles — birth, state transitions, health monitoring, and death. Designed for fleet management of autonomous agents.

## Installation

```bash
pip install agent-lifecycle
```

For development:

```bash
pip install -e ".[dev]"
pytest
```

## Quick Start

```python
from agent_lifecycle import AgentRegistry, AgentState

registry = AgentRegistry()

# Register a new agent
agent = registry.register("agent-42", metadata={"role": "worker"}, tags={"gpu"})

# Drive through lifecycle states
registry.transition("agent-42", AgentState.BORN)
registry.transition("agent-42", AgentState.ACTIVE)

# Query the fleet
active_agents = registry.list_active()
alive_agents = registry.list_alive()
summary = registry.summary()  # count per state

# Check health
unhealthy = registry.unhealthy(max_idle_seconds=300)
```

## Lifecycle States

Agents follow a defined state machine:

```
CONCEIVED → BORN → ACTIVE ⇄ IDLE
                  ↓       ↓
              SUSPENDED ←→ ACTIVE/IDLE
                  ↓
              RETIRED → DEAD
```

Any state can transition directly to `DEAD` (except `DEAD` itself, which is terminal).

## State Machine

```python
from agent_lifecycle import Lifecycle, AgentState

lc = Lifecycle(agent_id="agent-42")

# Check if a transition is valid
lc.can_transition(AgentState.BORN)  # True
lc.can_transition(AgentState.ACTIVE)  # False (must go through BORN first)

# Transition
lc.transition(AgentState.BORN)
lc.transition(AgentState.ACTIVE, metadata={"reason": "deployment"})

# Inspect history
for record in lc.history:
    print(f"{record.state.value} at {record.entered_at}")

# Force state (bypasses validation — use for recovery)
lc.force_state(AgentState.ACTIVE)
```

## Transition Guards & Side Effects

```python
from agent_lifecycle import StateTransition, AgentState

stm = StateTransition()

# Add a guard — agent must be registered before going active
def must_be_registered(agent_id, from_state, to_state):
    return agent_id in registry

stm.add_rule(
    AgentState.BORN, AgentState.ACTIVE,
    guards=[must_be_registered],
    side_effects=[lambda aid, f, t: print(f"{aid} is now active!")],
    rollback_fns=[lambda aid, f, t: cleanup(aid)],
)

result = stm.execute("agent-42", AgentState.BORN, AgentState.ACTIVE)
if result.success:
    print("Transition succeeded")
elif result.rolled_back:
    print("Side effect failed, rolled back")
```

## Heartbeat Monitoring

```python
from agent_lifecycle import HeartbeatMonitor, HeartbeatConfig, HealthStatus

config = HeartbeatConfig(interval_seconds=30.0, missed_threshold=3, degraded_factor=2.0)
monitor = HeartbeatMonitor(default_config=config)

monitor.register("agent-42")
monitor.beat("agent-42")  # call on each heartbeat

# Check health
status = monitor.check("agent-42")  # HEALTHY, DEGRADED, or UNRESPONSIVE

# Fleet-wide check
all_status = monitor.check_all()
unresponsive = monitor.unresponsive_agents()
```

## Audit Logging

```python
from agent_lifecycle import AuditLog, AuditEventType

# In-memory audit log
audit = AuditLog()

# Or with file persistence
audit = AuditLog(path="audit.jsonl")

# Record events
audit.record(AuditEventType.REGISTERED, agent_id="agent-42", message="Agent registered")
audit.record(AuditEventType.TRANSITION, agent_id="agent-42",
             message="born → active", details={"from": "born", "to": "active"})

# Query
events = audit.query(agent_id="agent-42")
transitions = audit.query(event_type=AuditEventType.TRANSITION)
recent = audit.query(since=time.time() - 3600, limit=10)

# Load from file
loaded = AuditLog.from_file("audit.jsonl")
```

## Full Integration Example

```python
from agent_lifecycle import *
import time

# Set up components
registry = AgentRegistry()
monitor = HeartbeatMonitor()
audit = AuditLog()

# Register an agent
registry.register("scout-1", metadata={"role": "recon"}, tags={"edge"})

# Lifecycle transitions (auto-logged)
for target in [AgentState.BORN, AgentState.ACTIVE]:
    registry.transition("scout-1", target)
    audit.record(AuditEventType.TRANSITION, agent_id="scout-1", message=f"→{target.value}")

# Start heartbeat monitoring
monitor.register("scout-1")
monitor.beat("scout-1")

# Later: check fleet health
if monitor.check("scout-1") == HealthStatus.UNRESPONSIVE:
    audit.record(AuditEventType.ALERT, agent_id="scout-1", message="Agent unresponsive")
    registry.transition("scout-1", AgentState.SUSPENDED)
```

## API Reference

### `AgentState` (Enum)

`CONCEIVED` · `BORN` · `ACTIVE` · `IDLE` · `SUSPENDED` · `RETIRED` · `DEAD`

### `Lifecycle(agent_id, initial_state=CONCEIVED, on_transition=None)`

- `current_state` — current `AgentState`
- `history` — list of `StateRecord` snapshots
- `can_transition(target)` — check if transition is valid
- `transition(target, metadata=None)` — perform state transition
- `force_state(target, metadata=None)` — bypass validation
- `is_terminal()` — is agent dead?
- `time_in_state()` — seconds since entering current state

### `AgentRegistry()`

- `register(agent_id, metadata=None, tags=None)` — register a new agent
- `deregister(agent_id)` — remove an agent
- `get(agent_id)` — retrieve agent record
- `transition(agent_id, target)` — transition agent state
- `touch(agent_id)` — update last-seen timestamp
- `list_agents(states=None, tags=None)` — filtered query
- `list_active()` / `list_alive()` — convenience queries
- `unhealthy(max_idle_seconds)` — agents past idle threshold
- `summary()` — `{AgentState: count}`

### `StateTransition()`

- `add_rule(from_state, to_state, guards=None, side_effects=None, rollback_fns=None)`
- `execute(agent_id, from_state, to_state, on_failure=None)` → `TransitionResult`
- `check(agent_id, from_state, to_state)` → error message or `None`

### `HeartbeatMonitor(default_config=None, on_status_change=None)`

- `register(agent_id, config=None)` — start monitoring
- `beat(agent_id)` — record a heartbeat
- `check(agent_id)` → `HealthStatus`
- `check_all()` → `{agent_id: HealthStatus}`
- `unresponsive_agents()` → list of agent IDs

### `HeartbeatConfig(interval_seconds=30, missed_threshold=3, degraded_factor=2.0)`

### `AuditLog(path=None)`

- `record(event_type, agent_id="", message="", details=None)` → `AuditEntry`
- `query(agent_id=None, event_type=None, since=None, until=None, limit=None)`
- `entries` — all recorded entries
- `clear()` — clear in-memory log

### `AuditEventType` (Enum)

`REGISTERED` · `DEREGISTERED` · `TRANSITION` · `HEARTBEAT` · `HEALTH_CHANGE` · `FORCE_STATE` · `ALERT` · `ERROR`

## License

MIT
