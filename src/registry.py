"""Agent lifecycle registry: register, track state transitions, deregister."""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class LifecycleState(Enum):
    BORN = "born"
    INITIALIZING = "initializing"
    READY = "ready"
    WORKING = "working"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"

@dataclass
class Transition:
    from_state: str
    to_state: str
    timestamp: float
    reason: str = ""

@dataclass
class AgentRecord:
    id: str
    name: str
    state: LifecycleState
    registered_at: float
    last_active: float
    transitions: list[Transition] = field(default_factory=list)

class Registry:
    """Track agent lifecycles: register, transition states, deregister."""
    
    def __init__(self):
        self.agents: dict[str, AgentRecord] = {}
    
    def register(self, name: str, metadata: dict = None) -> str:
        agent_id = str(uuid.uuid4())[:8]
        now = time.time()
        
        self.agents[agent_id] = AgentRecord(
            id=agent_id,
            name=name,
            state=LifecycleState.BORN,
            registered_at=now,
            last_active=now,
            transitions=[Transition("none", "born", now, "initial registration")]
        )
        
        if metadata:
            self.agents[agent_id].__dict__.update({"metadata": metadata})
        
        return agent_id
    
    def transition(self, agent_id: str, new_state: LifecycleState, reason: str = "") -> bool:
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        old_state = agent.state
        
        agent.state = new_state
        agent.last_active = time.time()
        agent.transitions.append(Transition(old_state.value, new_state.value, time.time(), reason))
        
        return True
    
    def deregister(self, agent_id: str, reason: str = "explicit_deregister") -> bool:
        return self.transition(agent_id, LifecycleState.TERMINATED, reason)
    
    def get_state(self, agent_id: str) -> Optional[LifecycleState]:
        if agent_id in self.agents:
            return self.agents[agent_id].state
        return None
    
    def list_agents(self, state_filter: Optional[LifecycleState] = None) -> list[dict]:
        result = []
        for aid, agent in self.agents.items():
            if state_filter is None or agent.state == state_filter:
                result.append({
                    "id": aid, "name": agent.name,
                    "state": agent.state.value,
                    "transitions": len(agent.transitions)
                })
        return result

if __name__ == "__main__":
    reg = Registry()
    
    # Register 3 agents
    a1 = reg.register("Scout-1", {"role": "recon"})
    a2 = reg.register("Scout-2", {"role": "recon"})
    a3 = reg.register("Worker-1", {"role": "build"})
    
    # Lifecycle transitions
    reg.transition(a1, LifecycleState.INITIALIZING, "bootstrapping")
    reg.transition(a1, LifecycleState.READY, "checks passed")
    reg.transition(a1, LifecycleState.WORKING, "task assigned")
    
    reg.transition(a3, LifecycleState.WORKING, "deployment started")
    reg.transition(a3, LifecycleState.SUSPENDED, "resource pressure")
    
    # List all
    print("All agents:", reg.list_agents())
    print("Working only:", reg.list_agents(LifecycleState.WORKING))
    
    # Deregister one
    reg.deregister(a2, "mission complete")
    print("After deregister:", reg.get_state(a2))