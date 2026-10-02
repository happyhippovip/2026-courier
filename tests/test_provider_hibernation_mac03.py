"""Deterministic fake-provider tests for Issue #75 MAC03 slice.

Covers the smallest coherent advance on top of
origin/feature/issue-75-provider-survival:

- 429/QUOTA_EXHAUSTED opens the circuit with reset metadata (incl. naive
  timestamps, which must not crash the scheduler path);
- duplicate scheduled wakes while OPEN cause zero provider calls and at
  most one recheck marker;
- LOCAL_READY work continues while provider-required work waits;
- authorized fallback preserves effect_key/attempt/dispatch identity;
- consequential-uncertain effects never auto-retry; Human Desk stays gated;
- customer projection never surfaces raw provider internals;
- quota-blocked/idle lane: checkpoint -> release -> HIBERNATED -> resume;
- after reset, exactly one bounded recovery probe fires;
- restart reconstructs lane truth deterministically.

No network, no real providers, no wall-clock sleeps. The fake provider is
``scheduler.recovery_probe`` / ``simulate_*`` hooks plus the in-memory
``provider_calls`` log.
"""

import datetime

import pytest

from scripts.automation_wake_coalescing import AutoState, AutomationContext, Wakeup
from scripts.provider_circuit import ProviderState
from scripts.provider_hibernation import (
    ContinuationCheckpoint,
    LaneHibernator,
    LaneState,
    should_hibernate,
)
from scripts.provider_survival import CourierScheduler, Provider, TaskContext


def _past_reset():
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)


def _future_reset():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)


def _blocked_scheduler():
    """Scheduler whose primary circuit is OPEN on quota, with no fallback."""
    sched = CourierScheduler()
    sched.providers = [Provider(id="muse", is_authorized=True, capabilities=["completion"])]
    sched.breaker.record_failure("muse", "default", "completion", 429, "subscription quota exhausted",
                                 reset_time=_future_reset())
    return sched


def _hibernator_with_resources(released_log):
    lane = LaneHibernator()
    lane.register_resource("provider:muse", "provider",
                           release_hook=lambda name: released_log.append(name))
    lane.register_resource("watcher:local", "watcher",
                           release_hook=lambda name: released_log.append(name))
    lane.register_resource("ui:hub", "ui",
                           release_hook=lambda name: released_log.append(name))
    lane.register_resource("pty:session-1", "pty",
                           release_hook=lambda name: released_log.append(name))
    lane.register_resource("human:desk", "human_desk", essential=True,
                           release_hook=lambda name: released_log.append(name))
    return lane


def _checkpoint():
    return ContinuationCheckpoint(
        stage="provider-blocked",
        repo_sha="abc123",
        task_id="t-prov",
        attempt=2,
        dispatch_id="d-1",
        effect_key="eff-1",
        open_provider_units=["t-prov"],
        provider_failure_class="QUOTA_EXHAUSTED",
        next_units=["t-prov"],
    )


def test_429_quota_exhausted_opens_circuit_with_reset():
    sched = CourierScheduler()
    sched.providers = [Provider(id="muse", is_authorized=True, capabilities=["completion"])]
    reset = _future_reset()
    sched.breaker.record_failure("muse", "default", "completion", 429,
                                 "subscription quota exhausted", reset_time=reset)
    circuit = sched.breaker.get_circuit("muse", "default", "completion")
    assert circuit.state == ProviderState.QUOTA_EXHAUSTED
    assert circuit.reset_time == reset
    assert sched.breaker.is_open("muse", "default", "completion") is True


def test_naive_reset_timestamp_does_not_crash_scheduler_path():
    sched = CourierScheduler()
    naive = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    assert naive.tzinfo is None
    sched.breaker.record_failure("muse", "default", "completion", 429, "quota exhausted",
                                 reset_time=naive)
    assert sched.breaker.is_open("muse", "default", "completion") is True


def test_100_duplicate_wakes_zero_provider_calls_single_marker():
    sched = _blocked_scheduler()
    task = TaskContext("t-prov", accepted_evidence="yes")

    ctx = AutomationContext()
    ctx.enqueue_wake(Wakeup(trigger_id="wake-0"))
    assert ctx.start_execution() is True
    for i in range(100):
        ctx.enqueue_wake(Wakeup(trigger_id=f"wake-{i}"))
    # Bounded by construction: a single boolean, never a 100-deep queue.
    assert ctx.recheck_needed is True
    ctx.finish_execution()
    assert ctx.recheck_needed is False

    for i in range(100):
        sched.handle_wake(f"wake-{i}", [task])
    assert sched.provider_calls == []
    assert "t-prov" not in sched.completed_tasks
    assert sched.evaluate_task_state(task).name == "WAITING_PROVIDER"


def test_local_ready_continues_while_quota_blocked():
    sched = _blocked_scheduler()
    t_provider = TaskContext("t-prov", accepted_evidence="yes")
    t_local = TaskContext("t-loc", is_deterministic=True, accepted_evidence="yes")
    sched.handle_wake("wake-1", [t_provider, t_local])
    assert "t-loc" in sched.completed_tasks
    assert "t-prov" not in sched.completed_tasks


def test_provider_required_waits_without_fallback():
    sched = _blocked_scheduler()
    task = TaskContext("t-prov", accepted_evidence="yes")
    assert sched.evaluate_task_state(task).name == "WAITING_PROVIDER"
    sched.handle_wake("wake-1", [task])
    assert sched.completed_tasks == []
    assert sched.provider_calls == []


def test_authorized_fallback_preserves_identity():
    sched = _blocked_scheduler()
    sched.providers = [
        Provider(id="muse", is_authorized=True, capabilities=["completion"]),
        Provider(id="gemini", is_authorized=True, capabilities=["completion"]),
    ]
    task = TaskContext("t-prov", effect_key="eff-1", attempt=2, dispatch_id="d-1")
    sched.handle_wake("wake-1", [task])
    # Handoff consumed immediately; task is not complete (no evidence)
    assert "t-prov" not in sched.completed_tasks
    assert len(sched.pending_handoffs) == 0
    assert ("gemini", "t-prov") in sched.provider_calls

    handoff = sched.router.create_compact_handoff(
        task, "muse", Provider(id="gemini", is_authorized=True, capabilities=["completion"]))
    assert handoff["EFFECT_KEY"] == "eff-1"
    assert handoff["ATTEMPT"] == 2
    assert handoff["DISPATCH_ID"] == "d-1"
    assert handoff["AUTHORITY_BOUNDARY"] == "PRESERVED"


def test_effect_uncertain_never_auto_retries():
    sched = _blocked_scheduler()
    sched.providers = [
        Provider(id="muse", is_authorized=True, capabilities=["completion"]),
        Provider(id="gemini", is_authorized=True, capabilities=["completion"]),
    ]
    task = TaskContext("t-eff", accepted_evidence="yes", effect_uncertain=True)
    sched.handle_wake("wake-1", [task])
    assert "t-eff" not in sched.completed_tasks


def test_human_desk_stays_gated_with_fallback():
    sched = _blocked_scheduler()
    sched.providers = [
        Provider(id="muse", is_authorized=True, capabilities=["completion"]),
        Provider(id="gemini", is_authorized=True, capabilities=["completion"]),
    ]
    task = TaskContext("t-hum", requires_human_gate=True)
    assert sched.evaluate_task_state(task).name == "WAITING_AUTHORITY"
    sched.handle_wake("wake-1", [task])
    assert "t-hum" not in sched.completed_tasks
    assert sched.customer_state([task]) == "NEEDS YOU"


def test_customer_projection_hides_raw_provider_internals():
    sched = _blocked_scheduler()
    blocked = TaskContext("t-prov", accepted_evidence="yes")
    assert sched.customer_state([blocked]) == "WORKING"
    assert "429" not in sched.customer_state([blocked])

    done_local = TaskContext("t-loc", is_deterministic=True, accepted_evidence="yes")
    sched.handle_wake("wake-1", [done_local])
    assert sched.customer_state([done_local]) == "DONE"


def test_quota_blocked_idle_lane_hibernates_and_releases():
    released = []
    lane = _hibernator_with_resources(released)
    report = lane.hibernate(_checkpoint())
    assert lane.state == LaneState.HIBERNATED
    assert sorted(report["released"]) == ["provider:muse", "pty:session-1", "ui:hub", "watcher:local"]
    assert report["retained"] == ["human:desk"]
    # Human Desk release hook must never fire.
    assert "human:desk" not in released


def test_hibernate_refused_with_local_work_or_fallback():
    assert should_hibernate(["t-loc"], ["t-prov"], True, False) is False
    assert should_hibernate([], ["t-prov"], False, False) is False
    assert should_hibernate([], ["t-prov"], True, True) is False
    assert should_hibernate([], [], True, False) is False
    assert should_hibernate([], ["t-prov"], True, False) is True

    sched = _blocked_scheduler()
    released = []
    lane = _hibernator_with_resources(released)
    local = TaskContext("t-loc", is_deterministic=True, accepted_evidence="yes")
    provider_task = TaskContext("t-prov", accepted_evidence="yes")
    assert sched.hibernate_if_quota_blocked_idle(
        lane, _checkpoint(), [local], [provider_task]) is None
    assert lane.state == LaneState.ACTIVE


def test_resume_restores_exact_checkpoint():
    released = []
    lane = _hibernator_with_resources(released)
    lane.hibernate(_checkpoint())
    restored = lane.resume()
    assert lane.state == LaneState.ACTIVE
    assert restored.task_id == "t-prov"
    assert restored.attempt == 2
    assert restored.dispatch_id == "d-1"
    assert restored.effect_key == "eff-1"
    assert restored.authority_boundary == "PRESERVED"


def test_restart_reconstructs_hibernated_lane():
    released = []
    lane = _hibernator_with_resources(released)
    lane.hibernate(_checkpoint())
    snapshot = lane.to_dict()
    rebuilt = LaneHibernator.from_dict(snapshot)
    assert rebuilt.state == LaneState.HIBERNATED
    assert rebuilt.checkpoint.task_id == "t-prov"
    assert rebuilt.resources["provider:muse"].released is True
    assert rebuilt.resources["human:desk"].essential is True
    assert rebuilt.resume().effect_key == "eff-1"


def test_single_bounded_recovery_probe_after_reset():
    sched = CourierScheduler()
    sched.providers = [Provider(id="muse", is_authorized=True, capabilities=["completion"])]
    sched.breaker.record_failure("muse", "default", "completion", 429, "quota exhausted",
                                 reset_time=_past_reset())
    circuit = sched.breaker.get_circuit("muse", "default", "completion")
    claims = []
    orig_claim = circuit.claim_probe
    circuit.claim_probe = lambda: (claims.append(1) or True) if orig_claim() else False

    tasks = [TaskContext(f"t-{i}", accepted_evidence="yes") for i in range(5)]
    sched.handle_wake("wake-1", tasks)
    # Exactly one bounded recovery probe; after re-arm the other 4 execute normally.
    # The probe task itself is NOT completed (probe != execution).
    assert len(claims) == 1
    assert len(sched.provider_calls) == 5
    assert sorted(sched.completed_tasks) == [f"t-{i}" for i in range(1, 5)]
    assert sched.breaker.get_circuit("muse", "default", "completion").state == ProviderState.AVAILABLE
    
    # Second wake: t-0 now executes normally
    sched.handle_wake("wake-2", tasks)
    assert sorted(sched.completed_tasks) == [f"t-{i}" for i in range(5)]


def test_failed_probe_reopens_circuit_without_completion():
    sched = CourierScheduler()
    sched.providers = [Provider(id="muse", is_authorized=True, capabilities=["completion"])]
    sched.breaker.record_failure("muse", "default", "completion", 429, "quota exhausted",
                                 reset_time=_past_reset())
    sched.recovery_probe = lambda: (False, 429, "still exhausted")
    task = TaskContext("t-prov", accepted_evidence="yes")
    for i in range(5):
        sched.handle_wake(f"wake-{i}", [task])
    assert sched.provider_calls == [("muse", "t-prov")]
    assert "t-prov" not in sched.completed_tasks
    assert sched.breaker.is_open("muse", "default", "completion") is True
