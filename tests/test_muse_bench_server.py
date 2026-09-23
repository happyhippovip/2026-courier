import json
import os
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path
import pytest

import scripts.muse_bench_server as server_mod


@pytest.fixture(autouse=True)
def isolate_workhorse(tmp_path, monkeypatch):
    work_dir = tmp_path / "muse_workhorse"
    monkeypatch.setattr(server_mod, "WORK_DIR", work_dir)
    monkeypatch.setattr(server_mod, "QUEUE_FILE", work_dir / "queue.jsonl")
    monkeypatch.setattr(server_mod, "RESULTS_DIR", work_dir / "results")
    monkeypatch.setattr(server_mod, "CHECKPOINT_FILE", work_dir / "checkpoint.json")
    monkeypatch.setattr(server_mod, "LEASE_DIR", work_dir / "lease")
    monkeypatch.setattr(server_mod, "LOCK_TTL_SECONDS", 2)
    server_mod.ensure_dirs()
    yield work_dir


def test_sanitize_task_id():
    assert server_mod.sanitize_task_id("valid-task_123") == "valid-task_123"
    assert server_mod.sanitize_task_id("../../etc/passwd") == "etcpasswd"
    assert server_mod.sanitize_task_id("").startswith("muse-")


def test_append_and_read_queue():
    envelope = {"slot": "CHAT 1", "template_id": "REVENUE", "prompt": "Identify pilot"}
    rec = server_mod.append_task(envelope)
    assert rec["state"] == "QUEUED"
    assert rec["template_id"] == "REVENUE"

    queue = server_mod.read_queue()
    assert len(queue) == 1
    assert queue[0]["task_id"] == rec["task_id"]
    assert queue[0]["state"] == "QUEUED"


def test_claim_task_and_concurrency():
    server_mod.append_task({"task_id": "task-1", "prompt": "Work 1"})
    server_mod.append_task({"task_id": "task-2", "prompt": "Work 2"})

    claimed1 = server_mod.claim_task("runner-A")
    assert claimed1 is not None
    assert claimed1["task_id"] == "task-1"
    assert claimed1["state"] == "RUNNING"
    assert claimed1["runner_id"] == "runner-A"

    # Second claim while lock held should be refused
    claimed2 = server_mod.claim_task("runner-B")
    assert claimed2 is None

    # Release lock
    assert server_mod.release_runner_lock("runner-A") is True

    # Now second task can be claimed
    claimed3 = server_mod.claim_task("runner-B")
    assert claimed3 is not None
    assert claimed3["task_id"] == "task-2"
    assert claimed3["state"] == "RUNNING"

    server_mod.release_runner_lock("runner-B")


def test_stale_lock_recovery():
    server_mod.append_task({"task_id": "task-stale", "prompt": "Stale test"})

    # Create stale lock file manually
    lock_file = server_mod.LEASE_DIR / "runner.lock"
    lock_file.write_text(json.dumps({"runner_id": "dead-runner", "at": time.time() - 10}))

    # Claim should notice stale lock, unlink, and claim task
    claimed = server_mod.claim_task("new-runner")
    assert claimed is not None
    assert claimed["task_id"] == "task-stale"
    assert claimed["runner_id"] == "new-runner"

    server_mod.release_runner_lock("new-runner")


def test_complete_task_with_result():
    rec = server_mod.append_task({"task_id": "task-comp", "prompt": "Complete test"})
    claimed = server_mod.claim_task("runner-comp")
    assert claimed is not None

    result_payload = {"material_findings": "Success", "sources": ["doc.md"]}
    ok = server_mod.complete_task("task-comp", result_payload)
    assert ok is True

    # Verify task updated in queue
    tasks = server_mod.read_queue()
    comp_task = next(t for t in tasks if t["task_id"] == "task-comp")
    assert comp_task["state"] == "COMPLETED"
    assert "completed_at" in comp_task

    # Verify result file saved
    res_file = server_mod.RESULTS_DIR / "task-comp.json"
    assert res_file.exists()
    assert json.loads(res_file.read_text(encoding="utf-8")) == result_payload

    # Verify runner lock was released
    assert not (server_mod.LEASE_DIR / "runner.lock").exists()


@pytest.fixture
def running_server():
    server = HTTPServer(("127.0.0.1", 0), server_mod.Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_http_api_endpoints(running_server):
    # GET /api/muse/state
    req = urllib.request.urlopen(f"{running_server}/api/muse/state")
    assert req.status == 200
    state = json.loads(req.read().decode("utf-8"))
    assert "queue" in state
    assert "results" in state
    assert "contract" in state

    # POST /api/muse/queue
    data = json.dumps({"slot": "TEST", "template_id": "AI_TO_CLI", "prompt": "replace AI"}).encode("utf-8")
    req = urllib.request.Request(f"{running_server}/api/muse/queue", data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    q_res = json.loads(resp.read().decode("utf-8"))
    assert q_res["ok"] is True
    tid = q_res["task"]["task_id"]

    # POST /api/muse/claim
    claim_data = json.dumps({"runner_id": "test-http-runner"}).encode("utf-8")
    req = urllib.request.Request(f"{running_server}/api/muse/claim", data=claim_data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    claim_res = json.loads(resp.read().decode("utf-8"))
    assert claim_res["ok"] is True
    assert claim_res["task"]["task_id"] == tid

    # POST /api/muse/complete
    comp_data = json.dumps({"task_id": tid, "result": {"findings": "verified"}}).encode("utf-8")
    req = urllib.request.Request(f"{running_server}/api/muse/complete", data=comp_data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    comp_res = json.loads(resp.read().decode("utf-8"))
    assert comp_res["ok"] is True
