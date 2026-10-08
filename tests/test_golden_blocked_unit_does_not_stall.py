"""A unit that cannot continue must not stall the units queued behind it.

Two cases, one worker host, no restart and no human resolve:

- FAILED: unit A crashes. The verifier rejects that result as non-retryable
  and the controller journals TASK_FAILED. The same worker then accepts B and C.
- BLOCKED: unit A is non-idempotent and its attempt has started. The worker
  that holds that lease vanishes (no further heartbeat), so the lease expires
  and the controller journals TASK_BLOCKED. A needs a human decision and is
  not retried. A different host, started once, accepts B and C while A stays
  BLOCKED. The hub model puts A in needs-you and B and C in done.
"""

import json
import sys
from pathlib import Path

import pytest

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
if str(_GOLDEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDEN_DIR))

import test_golden_happy
from courier_hub import model
from golden_harness import Courier, missing_modules, pids_alive

LEASE_TTL_S = 6
VANISHED_WORKER = "vanished-worker"

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


def _of_type(events, event_type):
    return [event for event in events if event["type"] == event_type]


def _one(events, event_type):
    matches = _of_type(events, event_type)
    assert len(matches) == 1, (event_type, [event["seq"] for event in matches])
    return matches[0]


def _dispatch_ids(events):
    return {event["dispatch_id"] for event in events if event["dispatch_id"]}


def _assert_accepted_once(courier, task_id):
    events = courier.task_events(task_id)
    types = [event_type for event_type in courier.task_types(task_id) if event_type != "TASK_PROGRESS"]
    assert types == test_golden_happy.GOLDEN_SEQUENCE, _diag(courier, events)
    assert len(_dispatch_ids(events)) == 1, _diag(courier, events)
    attempts = {event["attempt"] for event in events if event["attempt"] is not None}
    assert attempts == {1}, _diag(courier, events)
    ready = _one(events, "RESULT_READY")
    artifacts = json.loads(ready["payload"]).get("artifacts") or []
    assert len(artifacts) == 1, _diag(courier, ready)
    assert len(_of_type(events, "RESULT_ACCEPTED")) == 1
    return events


def _status(courier, task_id):
    response = courier.api.get(f"/v1/tasks/{task_id}")
    assert response.status_code == 200, _diag(courier, response.text)
    return response.json()


def test_failed_unit_does_not_stall_the_next_units(courier):
    courier.start_controller()
    # Attempts remain, but a crash is a non-retryable rejection: TASK_FAILED, no second effect.
    task_a = courier.make_task(
        effect_class="non_idempotent", max_attempts=3, crash_after_s=0, sleep_s=0,
    )
    task_b = courier.make_task()
    task_c = courier.make_task()
    worker = courier.start_worker()
    worker_pid = worker.pid

    _wait(courier, task_a, "TASK_FAILED", timeout=60)
    _wait(courier, task_c, "TASK_COMPLETE", timeout=90)

    events_a = courier.task_events(task_a)
    assert courier.worker.pid == worker_pid, _diag(courier, courier.worker.pid)
    assert courier.worker.poll() is None, _diag(courier, courier.worker.returncode)
    assert _status(courier, task_a)["status"] == "FAILED", _diag(courier, events_a)
    assert len(_of_type(events_a, "TASK_CLAIMED")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "RESULT_READY")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "RESULT_REJECTED")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "TASK_FAILED")) == 1, _diag(courier, events_a)
    assert _of_type(events_a, "TASK_RETRY_SCHEDULED") == [], _diag(courier, events_a)
    assert _of_type(events_a, "RESULT_ACCEPTED") == [], _diag(courier, events_a)
    assert _of_type(events_a, "TASK_COMPLETE") == [], _diag(courier, events_a)
    ready_a = _one(events_a, "RESULT_READY")
    assert json.loads(ready_a["payload"]).get("outcome") == "failure", _diag(courier, ready_a)
    assert len(_dispatch_ids(events_a)) == 1, _diag(courier, events_a)
    attempts_a = {event["attempt"] for event in events_a if event["attempt"] is not None}
    assert attempts_a == {1}, _diag(courier, events_a)

    events_b = _assert_accepted_once(courier, task_b)
    events_c = _assert_accepted_once(courier, task_c)
    claimed_a = _one(events_a, "TASK_CLAIMED")
    claimed_b = _one(events_b, "TASK_CLAIMED")
    claimed_c = _one(events_c, "TASK_CLAIMED")
    ready_b = _one(events_b, "RESULT_READY")
    assert claimed_a["worker_id"] == claimed_b["worker_id"] == claimed_c["worker_id"], _diag(
        courier, (claimed_a, claimed_b, claimed_c)
    )
    assert claimed_a["seq"] < ready_a["seq"] < claimed_b["seq"] < ready_b["seq"] < claimed_c["seq"], _diag(
        courier,
        (claimed_a["seq"], ready_a["seq"], claimed_b["seq"], ready_b["seq"], claimed_c["seq"]),
    )
    assert _status(courier, task_b)["status"] == "COMPLETE"
    assert _status(courier, task_c)["status"] == "COMPLETE"
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())
    print(
        f"DISPATCH_ID A={next(iter(_dispatch_ids(events_a)))} "
        f"B={next(iter(_dispatch_ids(events_b)))} "
        f"C={next(iter(_dispatch_ids(events_c)))}"
    )

    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    controller_pid = courier.controller.pid
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    leaked = pids_alive([*worker_tree, controller_pid])
    assert leaked == [], _diag(courier, leaked)
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())


def _events_for_hub(courier, task_id):
    rows = []
    for event in courier.task_events(task_id):
        row = dict(event)
        payload = row.get("payload")
        if isinstance(payload, str):
            row["payload"] = json.loads(payload or "{}")
        rows.append(row)
    return rows


def _hub_home(courier, task_ids):
    tasks = [_status(courier, task_id) for task_id in task_ids]
    events = {task_id: _events_for_hub(courier, task_id) for task_id in task_ids}
    return model.home(tasks, events)


def test_blocked_unit_does_not_stall_the_next_units(courier):
    """A started non-idempotent attempt whose lease is lost stays BLOCKED.

    The queue host is started once, after A is already running under a worker
    that never heartbeats again. That host is not killed and not replaced.
    """
    courier.start_controller()
    task_a = courier.make_task(
        effect_class="non_idempotent", max_attempts=3, lease_ttl_s=LEASE_TTL_S, hang=True,
    )
    lease = courier.api.post("/v1/claim", {"worker_id": VANISHED_WORKER})
    assert lease.status_code == 200, _diag(courier, lease.text)
    dispatch_a = lease.json()["dispatch_id"]
    started = courier.api.post("/v1/start", {"dispatch_id": dispatch_a})
    assert started.status_code == 200, _diag(courier, started.text)
    assert _status(courier, task_a)["status"] == "RUNNING"
    task_b = courier.make_task()
    task_c = courier.make_task()
    worker = courier.start_worker()
    worker_pid = worker.pid

    _wait(courier, task_a, "TASK_BLOCKED", timeout=LEASE_TTL_S + 20)
    _wait(courier, task_c, "TASK_COMPLETE", timeout=90)

    assert len(courier.workers) == 1
    assert courier.worker.pid == worker_pid, _diag(courier, courier.worker.pid)
    assert courier.worker.poll() is None, _diag(courier, courier.worker.returncode)

    events_a = courier.task_events(task_a)
    state_a = _status(courier, task_a)
    assert state_a["status"] == "BLOCKED", _diag(courier, events_a)
    assert state_a["attempt"] == 1, _diag(courier, state_a)
    assert len(_of_type(events_a, "TASK_CLAIMED")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "TASK_STARTED")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "LEASE_EXPIRED")) == 1, _diag(courier, events_a)
    assert len(_of_type(events_a, "TASK_BLOCKED")) == 1, _diag(courier, events_a)
    assert _of_type(events_a, "TASK_RETRY_SCHEDULED") == [], _diag(courier, events_a)
    assert _of_type(events_a, "RESULT_READY") == [], _diag(courier, events_a)
    assert _of_type(events_a, "RESULT_ACCEPTED") == [], _diag(courier, events_a)
    assert _of_type(events_a, "TASK_FAILED") == [], _diag(courier, events_a)
    assert _of_type(events_a, "TASK_COMPLETE") == [], _diag(courier, events_a)
    expired = _one(events_a, "LEASE_EXPIRED")
    blocked = _one(events_a, "TASK_BLOCKED")
    claimed_a = _one(events_a, "TASK_CLAIMED")
    started_a = _one(events_a, "TASK_STARTED")
    assert json.loads(expired["payload"]).get("reason") == "ttl", _diag(courier, expired)
    assert claimed_a["worker_id"] == VANISHED_WORKER
    assert len(_dispatch_ids(events_a)) == 1, _diag(courier, events_a)
    attempts_a = {event["attempt"] for event in events_a if event["attempt"] is not None}
    assert attempts_a == {1}, _diag(courier, events_a)
    assert claimed_a["seq"] < started_a["seq"] < expired["seq"] < blocked["seq"], _diag(
        courier, (claimed_a["seq"], started_a["seq"], expired["seq"], blocked["seq"])
    )

    events_b = _assert_accepted_once(courier, task_b)
    events_c = _assert_accepted_once(courier, task_c)
    claimed_b = _one(events_b, "TASK_CLAIMED")
    claimed_c = _one(events_c, "TASK_CLAIMED")
    ready_b = _one(events_b, "RESULT_READY")
    assert claimed_b["worker_id"] == claimed_c["worker_id"], _diag(courier, (claimed_b, claimed_c))
    assert claimed_b["worker_id"] != VANISHED_WORKER
    assert started_a["seq"] < claimed_b["seq"] < ready_b["seq"] < claimed_c["seq"], _diag(
        courier,
        (started_a["seq"], claimed_b["seq"], ready_b["seq"], claimed_c["seq"]),
    )
    assert _status(courier, task_a)["status"] == "BLOCKED"
    assert _status(courier, task_b)["status"] == "COMPLETE"
    assert _status(courier, task_c)["status"] == "COMPLETE"
    assert len(_of_type(courier.task_events(task_a), "TASK_CLAIMED")) == 1
    assert len(_of_type(courier.task_events(task_a), "TASK_STARTED")) == 1

    assert model.pile_of(state_a) == model.PILE_NEEDS_YOU
    assert model.pile_of(_status(courier, task_b)) == model.PILE_DONE
    assert model.pile_of(_status(courier, task_c)) == model.PILE_DONE
    view = _hub_home(courier, [task_a, task_b, task_c])
    assert [card["id"] for card in view["needs_you"]] == [task_a], _diag(courier, view)
    assert {card["id"] for card in view["done"]} == {task_b, task_c}, _diag(courier, view)
    assert view["working"] == [], _diag(courier, view)
    assert view["counts"] == {"needs_you": 1, "working": 0, "done": 2}
    assert view["needs_you"][0]["pile"] == model.PILE_NEEDS_YOU
    assert {card["pile"] for card in view["done"]} == {model.PILE_DONE}
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())
    print(
        f"DISPATCH_ID A={dispatch_a} "
        f"B={next(iter(_dispatch_ids(events_b)))} "
        f"C={next(iter(_dispatch_ids(events_c)))}"
    )

    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    controller_pid = courier.controller.pid
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    leaked = pids_alive([*worker_tree, controller_pid])
    assert leaked == [], _diag(courier, leaked)
    assert courier.outbox_files() == [], _diag(courier, courier.outbox_files())
