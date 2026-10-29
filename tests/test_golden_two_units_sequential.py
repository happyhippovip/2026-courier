"""Two authorized synthetic units complete back-to-back on one worker.

Proof that a single worker host, started once, drains a FIFO queue and also
picks up a unit that arrives while the first unit is still running. After the
worker starts, the queued-pair test only reads.
"""

import sys
from pathlib import Path

import pytest

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
if str(_GOLDEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDEN_DIR))

import test_golden_happy
from golden_harness import Courier, missing_modules, pids_alive

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
    return (
        f"{detail}\n"
        f"--- controller.log ---\n{courier.log_tail('controller.log')}\n"
        f"--- worker-0.log ---\n{courier.log_tail('worker-0.log')}\n"
        f"--- events ---\n{courier.all_events()}"
    )


def _wait(courier, task_id, event_type, timeout):
    try:
        return courier.wait_event(task_id, event_type, timeout=timeout)
    except AssertionError as exc:
        raise AssertionError(_diag(courier, str(exc))) from exc


def _one(events, event_type):
    matches = [event for event in events if event["type"] == event_type]
    assert len(matches) == 1, (event_type, [event["seq"] for event in matches])
    return matches[0]


def _assert_unit(courier, task_id):
    events = courier.task_events(task_id)
    types = [event_type for event_type in courier.task_types(task_id) if event_type != "TASK_PROGRESS"]
    assert types == test_golden_happy.GOLDEN_SEQUENCE, _diag(courier, events)
    dispatch_ids = {event["dispatch_id"] for event in events if event["dispatch_id"]}
    assert len(dispatch_ids) == 1, _diag(courier, dispatch_ids)
    attempts = {event["attempt"] for event in events if event["attempt"] is not None}
    assert attempts == {1}, _diag(courier, events)
    return events


def _assert_pair(courier, task_a, task_b):
    events_a = _assert_unit(courier, task_a)
    events_b = _assert_unit(courier, task_b)
    claimed_a = _one(events_a, "TASK_CLAIMED")
    claimed_b = _one(events_b, "TASK_CLAIMED")
    ready_a = _one(events_a, "RESULT_READY")
    assert claimed_a["worker_id"], _diag(courier, claimed_a)
    assert claimed_a["worker_id"] == claimed_b["worker_id"], _diag(courier, (claimed_a, claimed_b))
    assert claimed_a["seq"] < ready_a["seq"] < claimed_b["seq"], _diag(
        courier, (claimed_a["seq"], ready_a["seq"], claimed_b["seq"])
    )
    return claimed_a["worker_id"]


def _assert_worker_alive_then_stop(courier, worker_pid):
    assert courier.worker.pid == worker_pid, _diag(courier, (courier.worker.pid, worker_pid))
    assert courier.worker.poll() is None, _diag(courier, courier.worker.returncode)
    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    controller_pid = courier.controller.pid
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    assert pids_alive([*worker_tree, controller_pid]) == [], _diag(courier, pids_alive([*worker_tree, controller_pid]))
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())


def test_two_queued_units_run_back_to_back(courier):
    courier.start_controller()
    task_a = courier.make_task()
    task_b = courier.make_task()
    worker = courier.start_worker()
    worker_pid = worker.pid

    _wait(courier, task_b, "TASK_COMPLETE", timeout=90)
    _assert_pair(courier, task_a, task_b)
    _assert_worker_alive_then_stop(courier, worker_pid)


def test_unit_arriving_mid_run_is_picked_up_without_restart(courier):
    courier.start_controller()
    worker = courier.start_worker()
    worker_pid = worker.pid

    task_a = courier.make_task(sleep_s=3)
    _wait(courier, task_a, "TASK_STARTED", timeout=30)
    task_b = courier.make_task()
    _wait(courier, task_b, "TASK_COMPLETE", timeout=90)

    worker_id = _assert_pair(courier, task_a, task_b)
    assert len(courier.workers) == 1
    assert courier.worker.pid == worker_pid
    claimed = [event for event in courier.all_events() if event["type"] == "TASK_CLAIMED"]
    assert {event["worker_id"] for event in claimed} == {worker_id}
    _assert_worker_alive_then_stop(courier, worker_pid)
