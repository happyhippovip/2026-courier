import json
import os
import tempfile
import time

from scripts.orphan_task_reaper import check_task_health


def test_orphan_task_reaper_healthy():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        worker_file = os.path.join(tmp_dir, "worker_state.json")

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"tasks": {"T-VALID-1": {"status": "RUNNING"}}}, f)

        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({
                "current_task": {"task_id": "T-VALID-1"},
                "owned_pids": [],
                "last_heartbeat": time.time(),
            }, f)

        res = check_task_health(state_file=state_file, worker_state_file=worker_file)
        assert "T-VALID-1" in res["healthy_tasks"]
        assert "T-VALID-1" not in res["cleaned_tasks"]


def test_orphan_task_reaper_missing_canonical():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        worker_file = os.path.join(tmp_dir, "worker_state.json")

        # Empty state (no matching task)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"tasks": {}}, f)

        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({
                "current_task": {"task_id": "T-ORPHAN-1"},
                "owned_pids": [9999999],
                "last_heartbeat": time.time(),
            }, f)

        res = check_task_health(state_file=state_file, worker_state_file=worker_file)
        assert "T-ORPHAN-1" in res["cleaned_tasks"]

        with open(worker_file, "r", encoding="utf-8") as f:
            wstate = json.load(f)
        assert wstate["current_task"] is None
        assert wstate["owned_pids"] == []


def test_orphan_task_reaper_stale_heartbeat():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        worker_file = os.path.join(tmp_dir, "worker_state.json")

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"tasks": {"T-STALE-1": {"status": "RUNNING"}}}, f)

        # Heartbeat > 300 seconds in the past
        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({
                "current_task": {"task_id": "T-STALE-1"},
                "owned_pids": [],
                "last_heartbeat": time.time() - 400,
            }, f)

        res = check_task_health(state_file=state_file, worker_state_file=worker_file)
        assert "T-STALE-1" in res["cleaned_tasks"]


def test_orphan_task_reaper_dry_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        worker_file = os.path.join(tmp_dir, "worker_state.json")

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"tasks": {}}, f)

        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({
                "current_task": {"task_id": "T-ORPHAN-2"},
                "owned_pids": [],
            }, f)

        res = check_task_health(state_file=state_file, worker_state_file=worker_file, dry_run=True)
        assert "T-ORPHAN-2" in res["cleaned_tasks"]

        # Worker state was NOT mutated
        with open(worker_file, "r", encoding="utf-8") as f:
            wstate = json.load(f)
        assert wstate["current_task"]["task_id"] == "T-ORPHAN-2"
