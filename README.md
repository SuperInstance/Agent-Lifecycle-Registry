# agent-lifecycle-registry

Track agent lifecycles: registration, state transitions, and deregistration.

## Concept

Agents are born, transition through states (initializing → ready → working → suspended), and eventually terminate. The registry maintains the authoritative record.

## Usage

```bash
python src/registry.py
```

Output shows 3 agents registered, transitions, filtering by state, and deregistration.

## State Machine

```
born -> initializing -> ready -> working -> suspended -> terminated
         (boot)        (ready)   (task)    (wait)       (end)
```

## Registry Operations

| Method | Description |
|--------|-------------|
| register(name) | Create new agent record |
| transition(id, state) | Move agent to new state |
| deregister(id) | Mark agent terminated |
| get_state(id) | Query current state |
| list_agents(state_filter) | List with optional filter |