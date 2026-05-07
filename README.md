# Agent Lifecycle Registry

**Track agent lifecycles: registration, state transitions, and deregistration.**

![Status](https://img.shields.io/badge/Status-Functional-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)

Agents are born, they initialize, they do work, they suspend, and eventually they terminate. The registry maintains the authoritative record of every agent's current state and the full history of how it got there.

---

## Key Features

- **Complete State Machine** — 6 states: BORN → INITIALIZING → READY → WORKING → SUSPENDED → TERMINATED
- **Transition History** — Every state change is logged with timestamp and reason; audit trail is first-class
- **Metadata Attachments** — Register agents with arbitrary metadata (role, version, capabilities)
- **Filtered Queries** — List all agents, or filter by specific state (e.g., "show me all working agents")
- **Thread-Safe Transitions** — State changes update `last_active` and append to transition log atomically

---

## State Diagram

```
┌─────────┐     boot      ┌───────────────┐    ready     ┌─────────┐
│  BORN   │─────────────▶│ INITIALIZING   │─────────────▶│  READY  │
└─────────┘               └───────────────┘              └─────────┘
                               │                              │
                               │ bootstrap fail               │ task assigned
                               ▼                              ▼
                          ┌───────────┐                  ┌─────────┐
                          │ TERMINATED│◀─────────────────│ WORKING │
                          └───────────┘   terminated     └─────────┘
                               ▲                  ┌──────────┐
                               │                  │ SUSPENDED│
                               └──────────────────┤ (wait)   │
                                    resume        └──────────┘
```

| State | Meaning | Typical Duration |
|-------|---------|-----------------|
| `BORN` | Agent registered, not yet bootstrapping | < 1s |
| `INITIALIZING` | Bootstrapping, loading capabilities | seconds |
| `READY` | Checks passed, awaiting task assignment | until task |
| `WORKING` | Actively executing a task | varies |
| `SUSPENDED` | Paused (resource pressure, awaiting input) | varies |
| `TERMINATED` | Done — completed, failed, or explicitly killed | permanent |

---

## Usage

### Register an Agent

```python
from registry import Registry, LifecycleState

reg = Registry()
agent_id = reg.register("Scout-1", {"role": "recon", "version": "2.1"})
# Returns UUID string like "a1b2c3d4"
```

### Transition Through Lifecycle

```python
reg.transition(agent_id, LifecycleState.INITIALIZING, "bootstrapping")
reg.transition(agent_id, LifecycleState.READY, "checks passed")
reg.transition(agent_id, LifecycleState.WORKING, "task assigned")
reg.transition(agent_id, LifecycleState.SUSPENDED, "resource pressure")
# ... later ...
reg.transition(agent_id, LifecycleState.READY, "resources restored")
reg.transition(agent_id, LifecycleState.TERMINATED, "mission complete")
```

### Query State

```python
state = reg.get_state(agent_id)
print(state.value)  # "terminated"

# Find all working agents
working = reg.list_agents(state_filter=LifecycleState.WORKING)
for agent in working:
    print(agent["name"], agent["id"])
```

### Full Demo

```bash
python src/registry.py
```

Output:
```
All agents: [{'id': 'a1b2c3d4', 'name': 'Scout-1', 'state': 'working', 'transitions': 4}, ...]
Working only: [{'id': '...', 'name': 'Scout-1', 'state': 'working', 'transitions': 4}]
After deregister: <LifecycleState.TERMINATED: 'terminated'>
```

---

## Architecture

```
src/
└── registry.py
    ├── LifecycleState (Enum)
    │       BORN, INITIALIZING, READY, WORKING, SUSPENDED, TERMINATED
    │
    ├── Transition (dataclass)
    │       from_state, to_state, timestamp, reason
    │
    ├── AgentRecord (dataclass)
    │       id, name, state, registered_at, last_active, transitions[]
    │
    └── Registry
            ├── agents: dict[str, AgentRecord]
            ├── register(name, metadata) -> str        # returns agent_id
            ├── transition(agent_id, new_state) -> bool
            ├── deregister(agent_id, reason) -> bool
            ├── get_state(agent_id) -> LifecycleState
            └── list_agents(state_filter) -> list[dict]
```

### Registry Operations

| Method | Description |
|--------|-------------|
| `register(name, metadata?)` | Create new agent record, returns UUID |
| `transition(id, new_state, reason?)` | Move agent to new state, log transition |
| `deregister(id, reason?)` | Shortcut → transition to TERMINATED |
| `get_state(id)` | Query current state, returns None if not found |
| `list_agents(state_filter?)` | List all, or filter to specific state |

---

## Related Repos

- [fleet-agent](https://github.com/SuperInstance/fleet-agent) — Fleet orchestration, agents managed by registry
- [superinstance](https://github.com/SuperInstance/superinstance) — Agent collective framework
- [agent-forge](https://github.com/SuperInstance/agent-forge) — Agent onboarding and task assignment
- [zeroclaw-agent](https://github.com/SuperInstance/zeroclaw-agent) — Divergence tracking and consensus for fleet alignment
