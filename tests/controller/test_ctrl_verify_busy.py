"""A transient controller lock timeout must not strand a journaled result."""

import threading

import pytest

from ctrl_helpers import Verifiers, make_controller, run_attempt, task_body, types
from courier_core.controller import ApiError
from courier_core.verification import Verdict


@pytest.mark.parametrize("phase", ["load", "commit"])
@pytest.mark.parametrize("accepted", [True, False])
def test_busy_verification_remains_queued_until_one_durable_decision(tmp_path, phase, accepted):
    held, release = threading.Event(), threading.Event()
    holders = []
    calls = []

    def hold_lock():
        with ctl._locked():
            held.set()
            release.wait(5)

    def start_contention():
        thread = threading.Thread(target=hold_lock)
        holders.append(thread)
        thread.start()
        assert held.wait(2), "lock holder did not start"

    def verify(task, result, home):
        calls.append(result.result_id)
        if phase == "commit" and len(calls) == 1:
            start_contention()
        return Verdict(accepted, "independent proof", retryable=False)

    ctl = make_controller(tmp_path / "home", verifier=Verifiers(probe=verify), lock_timeout_s=0.01)
    try:
        _, body = ctl.create_task(task_body(max_attempts=1))
        task_id = body["task_id"]
        run_attempt(ctl)
        if phase == "load":
            start_contention()
        with pytest.raises(ApiError) as error:
            ctl.verify_next()
        assert error.value.code == "busy"
        release.set()
        for thread in holders:
            thread.join(2)
            assert not thread.is_alive()

        assert ctl.journal.task(task_id).status.value == "VERIFYING"
        assert "RESULT_ACCEPTED" not in types(ctl, task_id)
        assert "RESULT_REJECTED" not in types(ctl, task_id)
        # No restart, new worker result, or human "continue" is necessary.
        ctl.drain()
        expected = "COMPLETE" if accepted else "FAILED"
        assert ctl.journal.task(task_id).status.value == expected
        decision = "RESULT_ACCEPTED" if accepted else "RESULT_REJECTED"
        assert types(ctl, task_id).count(decision) == 1
        assert calls == ["r1"] * (1 if phase == "load" else 2)
        assert ctl.verify_next() is False
    finally:
        release.set()
        for thread in holders:
            thread.join(2)
        ctl.stop()
