"""Golden failure injections (architecture contract F, failure table).

Contract: tests/golden/README.md. Each case is an independent Courier home.
"""

import json
import sqlite3
import time

from golden_harness import GOLDEN_SHA256, open_handles, pids_alive, wait_until

LEASE_TTL_S = 6


def types_of(events):
    return [e["type"] for e in events if e["type"] != "TASK_PROGRESS"]


def payload(event):
    return json.loads(event["payload"] or "{}")


def accepted_events(courier, task_id):
    return [e for e in courier.task_events(task_id) if e["type"] == "RESULT_ACCEPTED"]


def test_kill_worker_mid_task_is_retried_once(courier):
    courier.start_controller()
    first = courier.start_worker()
    baseline_descendants = courier.settled_descendants(first)
    task_id = courier.make_task(hang=True, lease_ttl_s=LEASE_TTL_S)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)
    
    def new_descendants():
        current = set(courier.worker_descendants(first))
        return list(current - baseline_descendants)
        
    orphan_candidates = wait_until(new_descendants, 10, "attempt 1 child process")

    courier.kill_worker(first)
    courier.start_worker()

    expired = courier.wait_event(task_id, "LEASE_EXPIRED", timeout=LEASE_TTL_S + 20)
    assert payload(expired).get("reason") == "ttl", payload(expired)
    courier.wait_event(task_id, "TASK_RETRY_SCHEDULED", timeout=20)
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    assert complete["attempt"] == 2
    assert len(accepted_events(courier, task_id)) == 1
    wait_until(lambda: not pids_alive(orphan_candidates), 15, "children of the killed worker host to be gone")


def test_duplicate_result_is_acknowledged_without_new_events(courier):
    courier.start_controller()
    courier.start_worker()
    task_id = courier.make_task()
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    ready = next(e for e in courier.task_events(task_id) if e["type"] == "RESULT_READY")
    before = len(courier.all_events())

    response = courier.api.post("/v1/result", {
        "dispatch_id": ready["dispatch_id"],
        "result_id": ready["result_id"],
        "artifacts": payload(ready)["artifacts"],
        "outcome": "success",
    })
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACK_DUPLICATE"
    assert len(courier.all_events()) == before


def test_late_result_from_superseded_attempt_is_discarded(courier):
    courier.start_controller()
    task_id = courier.make_task(lease_ttl_s=LEASE_TTL_S)

    lease = courier.api.post("/v1/claim", {"worker_id": "golden-fake-worker"})
    assert lease.status_code == 200, lease.text
    stale_dispatch = lease.json()["dispatch_id"]
    assert courier.api.post("/v1/start", {"dispatch_id": stale_dispatch}).status_code == 200
    # no heartbeats: attempt 1 must expire, then the real worker runs attempt 2
    courier.wait_event(task_id, "LEASE_EXPIRED", timeout=LEASE_TTL_S + 20)
    courier.start_worker()
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    assert complete["attempt"] == 2

    late = courier.api.post("/v1/result", {
        "dispatch_id": stale_dispatch,
        "result_id": "late-result-attempt-1",
        "artifacts": [{"path": "out.txt", "sha256": GOLDEN_SHA256}],
        "outcome": "success",
    })
    assert late.status_code == 409, late.text
    courier.wait_event(task_id, "LATE_RESULT_DISCARDED", timeout=10)
    accepted = accepted_events(courier, task_id)
    assert len(accepted) == 1
    assert accepted[0]["attempt"] == 2
    assert accepted[0]["result_id"] != "late-result-attempt-1"


def test_timeout_kills_the_task_tree_and_retries(courier):
    courier.start_controller()
    worker = courier.start_worker()
    time.sleep(3)  # Allow worker to initialize Windows networking thread pools
    baseline_descendants = courier.settled_descendants(worker)
    baseline_handles = open_handles(worker.pid)
    task_id = courier.make_task(hang=True, timeout_s=3)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)
    
    def new_descendants():
        current = set(courier.worker_descendants(worker))
        return list(current - baseline_descendants)
        
    attempt1_tree = wait_until(new_descendants, 10, "attempt 1 child process")
    
    wait_until(lambda: not pids_alive(attempt1_tree), 3 + 5, "timed-out task tree to be killed")
    courier.wait_event(task_id, "TASK_RETRY_SCHEDULED", timeout=20)
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    assert complete["attempt"] == 2
    assert len(accepted_events(courier, task_id)) == 1
    time.sleep(2)
    assert open_handles(worker.pid) <= baseline_handles + 4, "worker host leaked handles/descriptors"


def test_cancel_while_running(courier):
    courier.start_controller()
    worker = courier.start_worker()
    baseline_descendants = courier.settled_descendants(worker)
    task_id = courier.make_task(hang=True)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)
    
    def new_descendants():
        current = set(courier.worker_descendants(worker))
        return list(current - baseline_descendants)
        
    tree = wait_until(new_descendants, 10, "running task child")

    assert courier.api.post(f"/v1/tasks/{task_id}/cancel").status_code == 200
    courier.wait_event(task_id, "TASK_CANCEL_REQUESTED", timeout=10)
    courier.wait_event(task_id, "TASK_CANCELLED", timeout=20)
    def is_tree_dead():
        alive = pids_alive(tree)
        if alive:
            print(f"DEBUG alive in tree: {alive}")
        return not alive
    wait_until(is_tree_dead, 10, "cancelled task tree to be killed")
    time.sleep(3)
    assert accepted_events(courier, task_id) == []
    assert "TASK_COMPLETE" not in types_of(courier.task_events(task_id))


def test_corrupt_journal_starts_degraded_and_read_only(courier):
    courier.start_controller()
    courier.start_worker()
    task_id = courier.make_task()
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()

    # tamper outside the controller: drop the append-only triggers (whatever they are
    # called), then change one stored payload while keeping it valid JSON
    conn = sqlite3.connect(str(courier.db_path))
    try:
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'events'").fetchall():
            conn.execute(f'DROP TRIGGER "{name}"')
        seq, body = conn.execute("SELECT seq, payload FROM events ORDER BY seq LIMIT 1 OFFSET 1").fetchone()
        tampered = json.loads(body or "{}")
        tampered["golden_tampered"] = True
        conn.execute("UPDATE events SET payload = ? WHERE seq = ?", (json.dumps(tampered), seq))
        conn.commit()
    finally:
        conn.close()

    courier.start_controller()
    health = courier.api.get("/v1/health").json()
    assert health["mode"] == "degraded_readonly", health
    assert isinstance(health.get("first_bad_seq"), int) and health["first_bad_seq"] <= seq, health
    refused = courier.api.post("/v1/tasks", {
        "adapter": "synthetic", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 6})
    assert refused.status_code == 503, refused.text


def test_controller_restart_mid_run_keeps_the_same_dispatch(courier):
    courier.start_controller()
    courier.start_worker()
    task_id = courier.make_task(sleep_s=8, lease_ttl_s=LEASE_TTL_S * 2)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)

    courier.kill_controller()
    courier.start_controller()
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)
    events = courier.task_events(task_id)
    assert "LEASE_EXPIRED" not in types_of(events)
    assert len({e["dispatch_id"] for e in events if e["dispatch_id"]}) == 1
    assert len(accepted_events(courier, task_id)) == 1


def test_restart_grace_expires_lease_when_worker_is_gone(courier):
    courier.start_controller()
    worker = courier.start_worker()
    task_id = courier.make_task(hang=True, lease_ttl_s=LEASE_TTL_S)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)

    courier.kill_worker(worker)
    courier.kill_controller()
    courier.start_controller()
    expired = courier.wait_event(task_id, "LEASE_EXPIRED", timeout=LEASE_TTL_S + 20)
    assert payload(expired).get("reason") == "restart_grace", payload(expired)


def test_transient_provider_failures_retry_until_success(courier):
    courier.start_controller()
    courier.start_worker()
    task_id = courier.make_task(fail_transient_n=2, max_attempts=3)
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=90)
    events = courier.task_events(task_id)
    assert types_of(events).count("RESULT_REJECTED") == 2
    assert complete["attempt"] == 3
    assert len(accepted_events(courier, task_id)) == 1


def test_non_idempotent_task_blocks_instead_of_retrying(courier):
    courier.start_controller()
    first = courier.start_worker()
    task_id = courier.make_task(hang=True, effect_class="non_idempotent", lease_ttl_s=LEASE_TTL_S)
    courier.wait_event(task_id, "TASK_STARTED", timeout=30)

    courier.kill_worker(first)
    courier.start_worker()
    courier.wait_event(task_id, "LEASE_EXPIRED", timeout=LEASE_TTL_S + 20)
    courier.wait_event(task_id, "TASK_BLOCKED", timeout=20)
    time.sleep(LEASE_TTL_S)
    claims = [e for e in courier.task_events(task_id) if e["type"] == "TASK_CLAIMED"]
    assert len(claims) == 1, "a non-idempotent task must never be claimed again automatically"
