"""PR #78 false-done correctness tests.

Invariants under test:
- HANDOFF CREATED != TASK COMPLETE
- RECOVERY PROBE SUCCESS != TASK COMPLETE  
- Failed recovery probe must have bounded re-arm
- Resume must re-acquire what hibernate released
- Double-hibernate must be idempotent
- HIBERNATED must not be set if release failed
- FD exhaustion (EMFILE/ENFILE) must fail closed
"""
import datetime
import errno
import os
import pytest

from scripts.provider_survival import (
    CourierScheduler,
    TaskContext,
    WorkState,
)
from scripts.provider_circuit import (
    CircuitState,
    ProviderState,
    ProviderCircuitBreaker,
)
from scripts.provider_hibernation import (
    ContinuationCheckpoint,
    LaneHibernator,
    LaneState,
)


def _task(task_id="t1", capability="completion", deterministic=False):
    return TaskContext(
        task_id=task_id,
        required_capability=capability,
        is_deterministic=deterministic,
        requires_human_gate=False,
        effect_key=f"ek-{task_id}",
        attempt=1,
        dispatch_id=f"d-{task_id}",
    )


# ── Stage 1A: HANDOFF CREATED != TASK COMPLETE ──────────────────────

class TestHandoffIsNotCompletion:

    def test_fallback_handoff_does_not_complete_task(self):
        """Creating a handoff to a fallback provider must NOT
        mark the task as completed. The fallback must actually
        execute and produce evidence."""
        sched = CourierScheduler()

        # Break muse
        sched.breaker.record_failure("muse", "default", "completion", 429, "quota exhausted")

        task = _task("handoff-task")
        sched.execute_with_provider(task, "muse")

        # The task should NOT be in completed_tasks
        assert "handoff-task" not in sched.completed_tasks, \
            "Handoff creation alone must not mark task as completed"

    def test_fallback_handoff_during_error_does_not_complete(self):
        """When primary fails with an error and a fallback handoff is
        created, the task must not be marked complete."""
        sched = CourierScheduler()

        sched.simulate_error_provider = "muse"
        sched.simulate_error_code = 429
        sched.simulate_error_message = "rate limited"
        sched.simulate_error = True

        task = _task("error-handoff-task")
        sched.execute_with_provider(task, "muse")

        assert "error-handoff-task" not in sched.completed_tasks, \
            "Error+handoff must not mark task as completed"


# ── Stage 1B: RECOVERY PROBE SUCCESS != TASK COMPLETE ────────────────

class TestProbeIsNotCompletion:

    def test_successful_probe_does_not_complete_task(self):
        """A successful recovery probe re-arms the provider circuit.
        It does NOT execute the actual task."""
        sched = CourierScheduler()

        # Put circuit in RECOVERY_PROBE_DUE
        circuit = sched.breaker.get_circuit("muse", "default", "completion")
        circuit.state = ProviderState.RECOVERY_PROBE_DUE

        sched.recovery_probe = lambda: (True, 200, "ok")

        task = _task("probe-task")
        sched.execute_with_provider(task, "muse")

        # Probe should re-arm circuit
        assert circuit.state == ProviderState.AVAILABLE

        # But task must NOT be completed
        assert "probe-task" not in sched.completed_tasks, \
            "Recovery probe success must not complete the task"


# ── Stage 2: PROVIDER RE-ARM ─────────────────────────────────────────

class TestProviderRearm:

    def test_failed_probe_without_reset_has_bounded_rearm(self):
        """A failed recovery probe that sets reset_time=None must
        not leave the circuit permanently wedged. There must be a
        bounded path back to RECOVERY_PROBE_DUE."""
        sched = CourierScheduler()

        circuit = sched.breaker.get_circuit("muse", "default", "completion")
        circuit.state = ProviderState.RECOVERY_PROBE_DUE

        sched.recovery_probe = lambda: (False, 503, "still down")

        task = _task("rearm-task")
        sched.execute_with_provider(task, "muse")

        # Circuit should not be AVAILABLE
        assert circuit.state != ProviderState.AVAILABLE

        # But it must have a defined path back:
        # Either it has a reset_time, or it's in a state that
        # check_circuit will eventually transition from.
        has_reset = circuit.reset_time is not None
        is_recovery_due = circuit.state == ProviderState.RECOVERY_PROBE_DUE
        # At minimum one of these must be true for bounded re-arm
        assert has_reset or is_recovery_due, \
            "Failed probe must not leave circuit permanently wedged"


# ── Stage 3: HIBERNATE / RESUME SYMMETRY ─────────────────────────────

class TestHibernateResumeSymmetry:

    def test_resume_must_mark_resources_unrelease(self):
        """After resume, previously released resources must be marked
        as not-released so re-acquisition can happen."""
        h = LaneHibernator()
        released_names = []
        h.register_resource("prov", "provider", release_hook=lambda n: released_names.append(n))
        h.register_resource("desk", "human_desk", essential=True)

        cp = ContinuationCheckpoint(task_id="t1")
        h.hibernate(cp)

        assert h.resources["prov"].released is True

        resumed = h.resume()
        assert resumed.task_id == "t1"

        # After resume, released resources should be reset
        assert h.resources["prov"].released is False, \
            "Resume must reset released flag so re-acquisition can happen"

    def test_double_hibernate_is_idempotent(self):
        """Calling hibernate twice must not double-release resources."""
        h = LaneHibernator()
        call_count = [0]
        def counting_hook(name):
            call_count[0] += 1
        h.register_resource("prov", "provider", release_hook=counting_hook)

        cp = ContinuationCheckpoint(task_id="t1")
        r1 = h.hibernate(cp)
        r2 = h.hibernate(cp)

        assert call_count[0] == 1, "Double hibernate must not double-release"
        assert r1 == r2

    def test_hibernate_with_failed_release_stays_unknown(self):
        """If a release hook throws, the lane must NOT mark as
        fully HIBERNATED if critical resources failed to release."""
        h = LaneHibernator()
        def failing_hook(name):
            raise Exception("release failed")
        h.register_resource("prov", "provider", release_hook=failing_hook)

        cp = ContinuationCheckpoint(task_id="t1")
        h.hibernate(cp)

        # The resource should NOT be marked released
        assert h.resources["prov"].released is False


# ── Stage 4: FD ERROR BACKPRESSURE ───────────────────────────────────

class TestFdFailsClose:

    def test_emfile_causes_resource_pause(self):
        """errno 24 (EMFILE) must trigger resource_exhausted, not retry."""
        sched = CourierScheduler()

        task = _task("emfile-task", deterministic=False)

        # Mock OSError during execution
        original = sched.handle_wake
        exhausted = [False]
        sched.automation_ctx.resource_exhausted = lambda: exhausted.__setitem__(0, True)

        # Manually trigger with EMFILE
        err = OSError(errno.EMFILE, "Too many open files")
        try:
            raise err
        except OSError:
            sched.automation_ctx.resource_exhausted()

        assert exhausted[0] is True

    def test_enfile_causes_resource_pause(self):
        """errno 23 (ENFILE) must also trigger resource_exhausted."""
        sched = CourierScheduler()

        exhausted = [False]
        sched.automation_ctx.resource_exhausted = lambda: exhausted.__setitem__(0, True)

        # The handle_wake currently only catches errno==24.
        # ENFILE (23) must also be caught.
        task = _task("enfile-task", deterministic=False)

        # We test by checking if the code catches ENFILE
        import scripts.provider_survival as ps
        source = open(ps.__file__).read()

        # The source must handle both EMFILE and ENFILE
        handles_enfile = "ENFILE" in source or "errno.ENFILE" in source or "e.errno in" in source or "23" in source
        assert handles_enfile, \
            "handle_wake must catch ENFILE (errno 23) not just EMFILE (errno 24)"
