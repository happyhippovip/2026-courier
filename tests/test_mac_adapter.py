"""Mac thin-adapter proof: same core, Mac paths, browser-pollable snapshot."""
import json
import subprocess
import sys

from scripts.mac_adapter import MacAdapter


def test_adapter_seed_run_snapshot(tmp_path):
    adapter = MacAdapter(tmp_path)
    assert adapter.seed(5)["seeded"] == 5
    assert adapter.start(cooldown=0)["started"] is True
    adapter.run()
    snap = adapter.status()
    assert snap["platform"] == "darwin"
    assert snap["state"] == "COMPLETED"
    assert snap["task_counts"].get("DONE") == 5
    assert snap["invariants"]["DUPLICATE_EXECUTIONS"] == 0
    assert snap["invariants"]["LOST_RESULTS"] == 0
    assert snap["invariants"]["MAX_ACTIVE"] == 1
    assert snap["motor_file_mtime"] is not None


def test_adapter_pause_resume_stop(tmp_path):
    adapter = MacAdapter(tmp_path)
    adapter.seed(3)
    adapter.start(cooldown=0)
    adapter.step()
    adapter.pause()
    adapter2 = MacAdapter(tmp_path)
    assert adapter2.status()["state"] in ("PAUSED", "RUNNING")
    if adapter2.status()["state"] == "RUNNING":
        adapter2.pause()
        adapter2.step()
    assert MacAdapter(tmp_path).status()["state"] == "PAUSED"
    assert MacAdapter(tmp_path).resume()["resumed"] is True
    MacAdapter(tmp_path).run()
    snap = MacAdapter(tmp_path).status()
    assert snap["invariants"]["DONE"] == 3
    assert snap["invariants"]["DUPLICATE_EXECUTIONS"] == 0


def test_adapter_cli_status_json(tmp_path):
    out = subprocess.check_output(
        [sys.executable, "scripts/mac_adapter.py", "--state-dir",
         str(tmp_path), "status"], text=True)
    snap = json.loads(out)
    assert snap["platform"] == "darwin"
    assert snap["state"] == "IDLE"
    assert snap["state_dir"] == str(tmp_path)
