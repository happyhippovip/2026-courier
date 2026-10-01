"""Golden path: one synthetic task end-to-end, clean shutdown, restart, replay.

Contract: tests/golden/README.md (architecture contract F, success path).
"""

import json

from golden_harness import GOLDEN_SHA256, pids_alive

GOLDEN_SEQUENCE = [
    "TASK_CREATED",
    "TASK_CLAIMED",
    "TASK_STARTED",
    "RESULT_READY",
    "RESULT_ACCEPTED",
    "TASK_COMPLETE",
]


def test_golden_happy_path_restart_and_replay(courier, tmp_path):
    courier.start_controller()
    courier.start_worker()

    task_id = courier.make_task()
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)

    # 1. exact lifecycle, one dispatch, first attempt
    events = courier.task_events(task_id)
    assert courier.task_types(task_id) == GOLDEN_SEQUENCE
    dispatch_ids = {e["dispatch_id"] for e in events if e["dispatch_id"]}
    assert len(dispatch_ids) == 1, dispatch_ids
    assert {e["attempt"] for e in events if e["attempt"] is not None} == {1}

    # 2. the accepted artifact is the synthetic content
    ready = next(e for e in events if e["type"] == "RESULT_READY")
    artifacts = json.loads(ready["payload"])["artifacts"]
    assert any(a.get("sha256") == GOLDEN_SHA256 for a in artifacts), artifacts

    # 3. the SSE stream delivers exactly the journal sequence
    all_seqs = [e["seq"] for e in courier.all_events()]
    assert courier.read_sse_seqs(until_seq=all_seqs[-1]) == all_seqs

    # 4. clean shutdown: no surviving processes, empty outbox
    live_hash = courier.projection_hash()
    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    controller_pid = courier.controller.pid
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    assert pids_alive([*worker_tree, controller_pid]) == []
    assert courier.outbox_files() == []

    # 5. offline: hash chain verifies and a full rebuild matches the live projection
    report, copy_hash, rebuilt_hash = courier.verify_and_rebuild(tmp_path)
    assert report.ok, report
    assert copy_hash == live_hash
    assert rebuilt_hash == live_hash

    # 6. restart: same final state, normal mode
    courier.start_controller()
    health = courier.api.get("/v1/health").json()
    assert health["mode"] == "normal", health
    assert courier.projection_hash() == live_hash
    assert courier.task_types(task_id) == GOLDEN_SEQUENCE
