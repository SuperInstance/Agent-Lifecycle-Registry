"""Tests for the agent_lifecycle package."""

import time
from pathlib import Path

import pytest

from agent_lifecycle import (
    AgentRegistry,
    AgentState,
    AuditEntry,
    AuditEventType,
    AuditLog,
    HeartbeatConfig,
    HeartbeatMonitor,
    HealthStatus,
    Lifecycle,
    StateTransition,
    TransitionError,
)


# ── Lifecycle ────────────────────────────────────────────────────────


class TestLifecycle:
    def test_initial_state_is_conceived(self):
        lc = Lifecycle(agent_id="a1")
        assert lc.current_state == AgentState.CONCEIVED

    def test_valid_transition(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.BORN)
        assert lc.current_state == AgentState.BORN

    def test_invalid_transition_raises(self):
        lc = Lifecycle(agent_id="a1")
        with pytest.raises(TransitionError):
            lc.transition(AgentState.ACTIVE)  # can't skip BORN

    def test_full_happy_path(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.BORN)
        lc.transition(AgentState.ACTIVE)
        lc.transition(AgentState.IDLE)
        lc.transition(AgentState.ACTIVE)
        lc.transition(AgentState.RETIRED)
        lc.transition(AgentState.DEAD)
        assert lc.current_state == AgentState.DEAD
        assert lc.is_terminal()

    def test_suspended_path(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.BORN)
        lc.transition(AgentState.ACTIVE)
        lc.transition(AgentState.SUSPENDED)
        lc.transition(AgentState.IDLE)
        assert lc.current_state == AgentState.IDLE

    def test_conceived_to_dead(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.DEAD)
        assert lc.is_terminal()

    def test_cannot_transition_from_dead(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.BORN)
        lc.transition(AgentState.DEAD)
        with pytest.raises(TransitionError):
            lc.transition(AgentState.ACTIVE)

    def test_can_transition(self):
        lc = Lifecycle(agent_id="a1")
        assert lc.can_transition(AgentState.BORN)
        assert not lc.can_transition(AgentState.ACTIVE)

    def test_force_state(self):
        lc = Lifecycle(agent_id="a1")
        lc.force_state(AgentState.ACTIVE)
        assert lc.current_state == AgentState.ACTIVE

    def test_history(self):
        lc = Lifecycle(agent_id="a1")
        lc.transition(AgentState.BORN)
        lc.transition(AgentState.ACTIVE)
        assert len(lc.history) == 3
        assert lc.history[0].state == AgentState.CONCEIVED
        assert lc.history[2].state == AgentState.ACTIVE

    def test_metadata_on_transition(self):
        lc = Lifecycle(agent_id="a1")
        rec = lc.transition(AgentState.BORN, metadata={"reason": "deploy"})
        assert rec.metadata["reason"] == "deploy"

    def test_time_in_state(self):
        lc = Lifecycle(agent_id="a1")
        before = time.time()
        time.sleep(0.01)
        elapsed = lc.time_in_state()
        assert elapsed > 0

    def test_on_transition_callback(self):
        calls = []
        def cb(aid, old, new):
            calls.append((aid, old, new))

        lc = Lifecycle(agent_id="a1", on_transition=cb)
        lc.transition(AgentState.BORN)
        assert len(calls) == 1
        assert calls[0] == ("a1", AgentState.CONCEIVED, AgentState.BORN)

    def test_repr(self):
        lc = Lifecycle(agent_id="a1")
        assert "a1" in repr(lc)
        assert "conceived" in repr(lc)


# ── Registry ─────────────────────────────────────────────────────────


class TestRegistry:
    def test_register_and_get(self):
        reg = AgentRegistry()
        rec = reg.register("a1", metadata={"role": "worker"})
        assert rec.agent_id == "a1"
        assert reg.get("a1") is rec

    def test_duplicate_registration_raises(self):
        reg = AgentRegistry()
        reg.register("a1")
        with pytest.raises(ValueError, match="already registered"):
            reg.register("a1")

    def test_deregister(self):
        reg = AgentRegistry()
        reg.register("a1")
        removed = reg.deregister("a1")
        assert removed.agent_id == "a1"
        assert "a1" not in reg

    def test_deregister_missing_raises(self):
        reg = AgentRegistry()
        with pytest.raises(KeyError):
            reg.deregister("ghost")

    def test_get_missing_raises(self):
        reg = AgentRegistry()
        with pytest.raises(KeyError):
            reg.get("ghost")

    def test_contains(self):
        reg = AgentRegistry()
        reg.register("a1")
        assert "a1" in reg
        assert "a2" not in reg

    def test_len(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.register("a2")
        assert len(reg) == 2

    def test_transition(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.transition("a1", AgentState.BORN)
        assert reg.get("a1").lifecycle.current_state == AgentState.BORN

    def test_list_agents_by_state(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.register("a2")
        reg.register("a3")
        reg.transition("a1", AgentState.BORN)
        reg.transition("a1", AgentState.ACTIVE)
        reg.transition("a2", AgentState.BORN)
        active = reg.list_agents(states={AgentState.ACTIVE})
        assert len(active) == 1
        assert active[0].agent_id == "a1"

    def test_list_agents_by_tag(self):
        reg = AgentRegistry()
        reg.register("a1", tags={"worker", "gpu"})
        reg.register("a2", tags={"worker"})
        reg.register("a3", tags={"monitor"})
        result = reg.list_agents(tags={"gpu"})
        assert len(result) == 1

    def test_list_active(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.register("a2")
        reg.transition("a1", AgentState.BORN)
        reg.transition("a1", AgentState.ACTIVE)
        reg.transition("a2", AgentState.BORN)
        assert len(reg.list_active()) == 1

    def test_list_alive(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.register("a2")
        reg.transition("a1", AgentState.BORN)
        reg.transition("a1", AgentState.DEAD)
        reg.transition("a2", AgentState.BORN)
        alive = reg.list_alive()
        assert len(alive) == 1
        assert alive[0].agent_id == "a2"

    def test_touch(self):
        reg = AgentRegistry()
        reg.register("a1")
        rec = reg.get("a1")
        old_seen = rec.last_seen
        time.sleep(0.01)
        reg.touch("a1")
        assert rec.last_seen > old_seen

    def test_unhealthy(self):
        reg = AgentRegistry()
        reg.register("a1")
        rec = reg.get("a1")
        rec.last_seen = time.time() - 600  # 10 min ago
        unhealthy = reg.unhealthy(max_idle_seconds=300)
        assert len(unhealthy) == 1

    def test_summary(self):
        reg = AgentRegistry()
        reg.register("a1")
        reg.register("a2")
        reg.transition("a1", AgentState.BORN)
        reg.transition("a1", AgentState.ACTIVE)
        summary = reg.summary()
        assert summary[AgentState.ACTIVE] == 1
        assert summary[AgentState.CONCEIVED] == 1


# ── StateTransition ──────────────────────────────────────────────────


class TestStateTransition:
    def test_no_rules_allows(self):
        stm = StateTransition()
        result = stm.execute("a1", AgentState.BORN, AgentState.ACTIVE)
        assert result.success

    def test_guard_blocks(self):
        stm = StateTransition()
        stm.add_rule(
            AgentState.BORN, AgentState.ACTIVE,
            guards=[lambda aid, f, t: False],
        )
        result = stm.execute("a1", AgentState.BORN, AgentState.ACTIVE)
        assert not result.success
        assert "Guard" in (result.error or "")

    def test_guard_passes(self):
        stm = StateTransition()
        stm.add_rule(
            AgentState.BORN, AgentState.ACTIVE,
            guards=[lambda aid, f, t: True],
        )
        result = stm.execute("a1", AgentState.BORN, AgentState.ACTIVE)
        assert result.success

    def test_side_effect_runs(self):
        calls = []
        stm = StateTransition()
        stm.add_rule(
            AgentState.BORN, AgentState.ACTIVE,
            side_effects=[lambda aid, f, t: calls.append((aid, f, t))],
        )
        stm.execute("a1", AgentState.BORN, AgentState.ACTIVE)
        assert len(calls) == 1

    def test_side_effect_failure_rollback(self):
        rollback_calls = []
        stm = StateTransition()
        stm.add_rule(
            AgentState.BORN, AgentState.ACTIVE,
            side_effects=[lambda aid, f, t: (_ for _ in ()).throw(RuntimeError("boom"))],
            rollback_fns=[lambda aid, f, t: rollback_calls.append(aid)],
        )
        result = stm.execute("a1", AgentState.BORN, AgentState.ACTIVE)
        assert not result.success
        assert result.rolled_back
        assert "a1" in rollback_calls

    def test_on_failure_callback(self):
        errors = []
        stm = StateTransition()
        stm.add_rule(
            AgentState.BORN, AgentState.ACTIVE,
            guards=[lambda aid, f, t: False],
        )
        stm.execute("a1", AgentState.BORN, AgentState.ACTIVE, on_failure=lambda e: errors.append(e))
        assert len(errors) == 1

    def test_get_rule(self):
        stm = StateTransition()
        rule = stm.add_rule(AgentState.BORN, AgentState.ACTIVE)
        assert stm.get_rule(AgentState.BORN, AgentState.ACTIVE) is rule
        assert stm.get_rule(AgentState.ACTIVE, AgentState.IDLE) is None

    def test_rules_property(self):
        stm = StateTransition()
        stm.add_rule(AgentState.BORN, AgentState.ACTIVE)
        stm.add_rule(AgentState.ACTIVE, AgentState.IDLE)
        assert len(stm.rules) == 2


# ── HeartbeatMonitor ─────────────────────────────────────────────────


class TestHeartbeatMonitor:
    def test_register_and_beat(self):
        mon = HeartbeatMonitor()
        mon.register("a1")
        mon.beat("a1")
        assert mon.check("a1") == HealthStatus.HEALTHY

    def test_unregistered_beat_raises(self):
        mon = HeartbeatMonitor()
        with pytest.raises(KeyError):
            mon.beat("ghost")

    def test_check_missing_raises(self):
        mon = HeartbeatMonitor()
        with pytest.raises(KeyError):
            mon.check("ghost")

    def test_degraded_status(self):
        cfg = HeartbeatConfig(interval_seconds=1.0, degraded_factor=2.0, missed_threshold=10)
        mon = HeartbeatMonitor(default_config=cfg)
        mon.register("a1")
        rec = mon._records["a1"]
        rec.last_heartbeat = time.time() - 3.0  # > 1.0 * 2.0, < 1.0 * 10
        assert mon.check("a1") == HealthStatus.DEGRADED

    def test_unresponsive_status(self):
        cfg = HeartbeatConfig(interval_seconds=1.0, missed_threshold=3)
        mon = HeartbeatMonitor(default_config=cfg)
        mon.register("a1")
        rec = mon._records["a1"]
        rec.last_heartbeat = time.time() - 10.0
        assert mon.check("a1") == HealthStatus.UNRESPONSIVE

    def test_check_all(self):
        mon = HeartbeatMonitor()
        mon.register("a1")
        mon.register("a2")
        mon.beat("a1")
        statuses = mon.check_all()
        assert "a1" in statuses
        assert "a2" in statuses

    def test_unresponsive_agents(self):
        cfg = HeartbeatConfig(interval_seconds=1.0, missed_threshold=2)
        mon = HeartbeatMonitor(default_config=cfg)
        mon.register("a1")
        mon.register("a2")
        mon.beat("a1")
        rec = mon._records["a2"]
        rec.last_heartbeat = time.time() - 100.0
        unresp = mon.unresponsive_agents()
        assert "a2" in unresp
        assert "a1" not in unresp

    def test_deregister(self):
        mon = HeartbeatMonitor()
        mon.register("a1")
        mon.deregister("a1")
        assert "a1" not in mon

    def test_mark_dead(self):
        mon = HeartbeatMonitor()
        mon.register("a1")
        mon.mark_dead("a1")
        assert "a1" not in mon

    def test_status_change_callback(self):
        changes = []
        def cb(aid, old, new):
            changes.append((aid, old, new))

        mon = HeartbeatMonitor(on_status_change=cb)
        mon.register("a1")
        mon.beat("a1")
        assert len(changes) == 1
        assert changes[0][0] == "a1"

    def test_contains_and_len(self):
        mon = HeartbeatMonitor()
        assert len(mon) == 0
        mon.register("a1")
        assert "a1" in mon
        assert len(mon) == 1


# ── AuditLog ─────────────────────────────────────────────────────────


class TestAuditLog:
    def test_record_and_query(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1", message="registered")
        log.record(AuditEventType.TRANSITION, agent_id="a1", message="born→active")
        assert len(log) == 2

    def test_query_by_agent(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1")
        log.record(AuditEventType.REGISTERED, agent_id="a2")
        results = log.query(agent_id="a1")
        assert len(results) == 1

    def test_query_by_event_type(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1")
        log.record(AuditEventType.TRANSITION, agent_id="a1")
        results = log.query(event_type=AuditEventType.TRANSITION)
        assert len(results) == 1

    def test_query_by_time_range(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1")
        t = time.time()
        log.record(AuditEventType.TRANSITION, agent_id="a1")
        results = log.query(since=t)
        assert len(results) == 1

    def test_query_with_limit(self):
        log = AuditLog()
        for i in range(10):
            log.record(AuditEventType.HEARTBEAT, agent_id=f"a{i}")
        results = log.query(limit=3)
        assert len(results) == 3

    def test_entries_property(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1")
        assert len(log.entries) == 1

    def test_clear(self):
        log = AuditLog()
        log.record(AuditEventType.REGISTERED, agent_id="a1")
        count = log.clear()
        assert count == 1
        assert len(log) == 0

    def test_file_persistence(self, tmp_path: Path):
        path = tmp_path / "audit.jsonl"
        log = AuditLog(path=path)
        log.record(AuditEventType.REGISTERED, agent_id="a1", message="hello")
        assert path.exists()

        loaded = AuditLog.from_file(path)
        assert len(loaded) == 1
        assert loaded.entries[0].agent_id == "a1"

    def test_entry_serialization(self):
        entry = AuditEntry(
            event_type=AuditEventType.TRANSITION,
            agent_id="a1",
            message="test",
            details={"from": "born", "to": "active"},
        )
        d = entry.to_dict()
        restored = AuditEntry.from_dict(d)
        assert restored.event_type == AuditEventType.TRANSITION
        assert restored.agent_id == "a1"
        assert restored.details["from"] == "born"


# ── Integration ──────────────────────────────────────────────────────


class TestIntegration:
    def test_full_lifecycle_with_audit(self):
        """End-to-end: register → lifecycle transitions → audit trail."""
        registry = AgentRegistry()
        audit = AuditLog()

        # Register
        registry.register("agent-x", metadata={"role": "scout"})
        audit.record(AuditEventType.REGISTERED, agent_id="agent-x", message="registered")

        # Lifecycle
        for target in [AgentState.BORN, AgentState.ACTIVE, AgentState.IDLE, AgentState.RETIRED, AgentState.DEAD]:
            registry.transition("agent-x", target)
            audit.record(
                AuditEventType.TRANSITION,
                agent_id="agent-x",
                message=f"→{target.value}",
            )

        assert registry.get("agent-x").lifecycle.is_terminal()
        assert len(audit.query(agent_id="agent-x")) == 6  # 1 register + 5 transitions

    def test_registry_with_heartbeat_and_audit(self):
        """Registry + heartbeat monitor + audit log working together."""
        registry = AgentRegistry()
        monitor = HeartbeatMonitor()
        audit = AuditLog()

        registry.register("h1")
        monitor.register("h1")
        audit.record(AuditEventType.REGISTERED, agent_id="h1")

        registry.transition("h1", AgentState.BORN)
        audit.record(AuditEventType.TRANSITION, agent_id="h1", message="→born")
        registry.transition("h1", AgentState.ACTIVE)
        audit.record(AuditEventType.TRANSITION, agent_id="h1", message="→active")

        monitor.beat("h1")
        audit.record(AuditEventType.HEARTBEAT, agent_id="h1", message="healthy")

        assert monitor.check("h1") == HealthStatus.HEALTHY
        assert len(registry.list_alive()) == 1
        assert len(audit) == 4  # registered + 2 transitions + heartbeat
