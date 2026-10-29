"""Restart recovery between two synthetic units.

Unit A and unit B are queued together. One test hard-kills the controller
after A's result is durable. The other hard-kills the worker after A is
complete. Each accepted result must happen once. This does not repeat the
back-to-back drain proof.
"""

import json
import sys
from pathlib import Path

import psutil
import pytest

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
if str(_GOLDEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDEN_DIR))

import test_golden_happy
from golden_harness import Courier, descendants, missing_modules, pids_alive

pytestmark = [
    pytest.mark.skipif(bool(missing_modules()), reason="golden v1 modules missing"),
]


@pytest.fixture
def courier(tmp_path):
    home = tmp_path / "courier_home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    instance = Courier(home, logs)
    yield instance
    instance.close()


def _diag(courier, detail):
    worker_log = "worker-0.log"
    if courier.workers:
        worker_log = f"worker-{len(courier.workers) - 1}.log"
    return (
        f"{detail}\n"
        f"--- controller.log ---\n{courier.log_tail('controller.log')}\n"
        f"--- {worker_log} ---\n{courier.log_tail(worker_log)}\n"
        f"--- events ---\n{courier.all_events()}"
    )


def _wait(courier, task_id, event_type, timeout):
    try:
        return courier.wait_event(task_id, event_type, timeout=timeout)
    except AssertionError as exc:
        raise AssertionError(_diag(courier, str(exc))) from exc


def _of_type(events, event_type):
    return [event for event in events if event["type"] == event_type]


def _one(events, event_type):
    matches = _of_type(events, event_type)
    assert len(matches) == 1, (event_type, [(event["seq"], event.get("attempt")) for event in matches])
    return matches[0]


def _snapshot(events):
    """Identity of journal rows. A restart must not rewrite these."""
    keys = ("seq", "type", "task_id", "attempt", "dispatch_id", "payload", "hash")
    return [tuple(event[key] for key in keys) for event in events]


def _dispatch_ids(events):
    return {event["dispatch_id"] for event in events if event["dispatch_id"]}


def _assert_once(events, event_type):
    assert len(_of_type(events, event_type)) == 1, (
        event_type,
        [(event["seq"], event.get("attempt"), event.get("dispatch_id")) for event in events],
    )


def _assert_no_second_artifact(events):
    ready = _one(events, "RESULT_READY")
    artifacts = json.loads(ready["payload"]).get("artifacts") or []
    assert len(artifacts) == 1, artifacts
    assert len(_of_type(events, "RESULT_READY")) == 1


def _kill_worker_tree(courier):
    """Hard-kill the live worker and every descendant the harness can see."""
    worker = courier.worker
    tree = [worker.pid, *descendants(worker.pid)]
    courier.tracked_pids.update(tree)
    courier.kill_worker(worker)
    for pid in pids_alive(tree):
        try:
            psutil.Process(pid).kill()
        except psutil.Error:
            pass
    return tree


def _finish_quiet(courier, extra_pids):
    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    controller_pid = courier.controller.pid
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    leaked = pids_alive([*worker_tree, controller_pid, *extra_pids])
    assert leaked == [], _diag(courier, leaked)
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())


def test_controller_restart_between_units(courier):
    courier.start_controller()
    task_a = courier.make_task()
    task_b = courier.make_task()
    courier.start_worker()

    _wait(courier, task_a, "RESULT_READY", timeout=60)
    b_claimed_at_kill = "TASK_CLAIMED" in courier.task_types(task_b)
    journal_before = _snapshot(courier.all_events())
    courier.kill_controller()
    courier.start_controller()

    _wait(courier, task_a, "TASK_COMPLETE", timeout=90)
    _wait(courier, task_b, "TASK_COMPLETE", timeout=90)

    survived = _snapshot(courier.all_events())
    missing = [row for row in journal_before if row not in survived]
    assert missing == [], _diag(courier, missing)

    events_a = courier.task_events(task_a)
    events_b = courier.task_events(task_b)
    assert courier.task_types(task_a) == test_golden_happy.GOLDEN_SEQUENCE, _diag(courier, events_a)
    _assert_once(events_a, "RESULT_ACCEPTED")
    _assert_once(events_a, "TASK_COMPLETE")
    _assert_no_second_artifact(events_a)
    dispatch_a = _dispatch_ids(events_a)
    assert len(dispatch_a) == 1, _diag(courier, dispatch_a)
    assert {event["attempt"] for event in events_a if event["attempt"] is not None} == {1}, _diag(
        courier, events_a
    )

    _assert_once(events_b, "RESULT_READY")
    _assert_once(events_b, "RESULT_ACCEPTED")
    _assert_once(events_b, "TASK_COMPLETE")
    _assert_no_second_artifact(events_b)
    dispatch_b = _dispatch_ids(events_b)
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())
    print(
        f"DISPATCH_ID A={next(iter(dispatch_a))} B={next(iter(dispatch_b))} "
        f"b_claimed_at_controller_kill={b_claimed_at_kill}"
    )
    _finish_quiet(courier, [])


def test_worker_restart_between_units(courier):
    courier.start_controller()
    task_a = courier.make_task()
    # B stays in flight if the worker claims it before the kill.
    task_b = courier.make_task(sleep_s=8)
    courier.start_worker()

    _wait(courier, task_a, "TASK_COMPLETE", timeout=60)
    events_a_before = courier.task_events(task_a)
    frozen = _snapshot(events_a_before)
    b_claimed_at_kill = "TASK_CLAIMED" in courier.task_types(task_b)
    killed = _kill_worker_tree(courier)
    courier.start_worker()

    _wait(courier, task_b, "TASK_COMPLETE", timeout=90)
    events_a = courier.task_events(task_a)
    assert _snapshot(events_a) == frozen, _diag(courier, (frozen, _snapshot(events_a)))
    assert courier.task_types(task_a) == test_golden_happy.GOLDEN_SEQUENCE, _diag(courier, events_a)

    events_b = courier.task_events(task_b)
    _assert_once(events_b, "RESULT_READY")
    _assert_once(events_b, "RESULT_ACCEPTED")
    _assert_once(events_b, "TASK_COMPLETE")
    _assert_no_second_artifact(events_b)
    attempts = {event["attempt"] for event in events_b if event["attempt"] is not None}
    if attempts != {1}:
        assert _of_type(events_b, "LEASE_EXPIRED"), _diag(courier, events_b)
    dispatch_a = _dispatch_ids(events_a)
    dispatch_b = _dispatch_ids(events_b)
    print(
        f"DISPATCH_ID A={next(iter(dispatch_a))} B={sorted(dispatch_b)} "
        f"b_claimed_at_worker_kill={b_claimed_at_kill} attempts_b={sorted(attempts)}"
    )
    _finish_quiet(courier, killed)
