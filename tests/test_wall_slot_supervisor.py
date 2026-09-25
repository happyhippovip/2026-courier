"""SIMULATED_SUPERVISOR_PROOF: stub workers under the real exit-code wrapper.

No Muse, no screen, no Mac: a FakeLauncher runs `bash -c` stubs as children.
"""
import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WALL = ROOT / "scripts" / "mac_worker" / "Terminal-Wall-BACKGROUND.py"
QUEUE = ROOT / "scripts" / "work_queue.py"
HEALTHY = {"swap_mb": 0.0, "load_1m": 0.5, "ws_cpu": 1.0, "sys_latency_ms": 1.0, "mem_pressure_pct": 80.0}
CRITICAL = dict(HEALTHY, mem_pressure_pct=5.0)


class Clock:
    def __init__(self): self.t = 1_000_000.0
    def __call__(self): return self.t


class FakeLauncher:
    """Runs the stub through the wall's own wrap_command; tracks children."""
    def __init__(self, wall):
        self.wall, self.procs, self.starts = wall, {}, []
    def start(self, slot_id, cmd):
        self.starts.append(slot_id)
        proc = subprocess.Popen(["bash", "-c", self.wall.wrap_command(slot_id, cmd)])
        self.procs[slot_id] = proc
        return str(proc.pid), "ttys-sim"
    def is_alive(self, slot_id, pid):
        proc = self.procs.get(slot_id)
        return bool(proc) and proc.poll() is None
    def existing(self, slot_id):
        proc = self.procs.get(slot_id)
        return str(proc.pid) if proc and proc.poll() is None else None
    def terminate(self, slot_id, pid):
        self.procs[slot_id].terminate()
    def wait_all(self):
        for proc in self.procs.values(): proc.wait(timeout=10)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    monkeypatch.setenv("COURIER_QUEUE_DIR", str(tmp_path / "queue"))
    spec = importlib.util.spec_from_file_location("wall_under_test", WALL)
    wall = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wall)
    (tmp_path / "wall").mkdir()
    with open(wall.STATE_FILE, "w", newline="") as f:  # generate_wall_state.py header
        w = csv.writer(f, delimiter="\t")
        w.writerow(["slot_id", "wid", "worker_type", "account_provider", "task_id", "scope", "state",
                    "claim_created_at", "pid", "pty", "proof_ref", "next_action", "blocker"])
        for i in range(1, 7):
            w.writerow([f"MUSE-{i:02d}", "", "muse", "default", "", "", "IDLE", "", "", "", "", "start", ""])
    for i in range(1, 9):
        subprocess.run([sys.executable, str(QUEUE), "--state-dir", str(tmp_path / "queue"), "add",
                        json.dumps({"task_id": f"T{i}", "package_id": "P", "description": "sim",
                                    "dependencies": [], "read_scopes": [], "status": "READY",
                                    "priority": i, "write_scopes": [f"scope-{i}"]})], check=True, capture_output=True)
    clock = Clock()
    launcher = FakeLauncher(wall)
    return wall, launcher, clock, tmp_path


def supervisor(wall, launcher, clock, target=4):
    wall.cmd_start(target, loop=False)
    gov = wall.CapacityGovernor(requested_max=target, start_capacity=target, clock=clock)
    return wall.Supervisor(launcher=launcher, governor=gov, clock=clock)


def use_stub(wall, script):
    cfg = wall.load_capacity_config()
    cfg["slot_command"] = script
    Path(wall.CONFIG_FILE).write_text(json.dumps(cfg))


def row(wall, slot):
    return next(r for r in wall.load_state() if r["slot_id"] == slot)


def test_normal_exit_restarts_same_slot_with_same_task_and_checkpoint(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, 'printf \'{"branch":"muse/x","last_commit":"abc123","next_task":"verify"}\' > {checkpoint}; exit 0')
    sup.tick(HEALTHY)
    first = row(wall, "MUSE-01")
    assert first["state"] == "WORKING" and first["task_id"] == "T1"
    launcher.wait_all()
    clock.t += 120
    sup.tick(HEALTHY)
    r = row(wall, "MUSE-01")
    assert r["state"] == "BACKOFF" and r["last_exit_code"] == "0" and r["restart_count"] == "1"
    assert (r["branch"], r["last_commit"], r["next_task"]) == ("muse/x", "abc123", "verify")
    assert r["task_id"] == "T1" and r["next_action"] == "resume_task"
    clock.t += wall.RESTART_BACKOFF + 1
    sup.tick(HEALTHY)
    r = row(wall, "MUSE-01")
    assert r["state"] == "WORKING" and r["task_id"] == "T1"
    assert launcher.starts.count("MUSE-01") == 2
    launcher.wait_all()


def test_proof_completes_task_and_next_start_claims_next_task(env):
    wall, launcher, clock, tmp = env
    sup = supervisor(wall, launcher, clock, target=4)
    proof = tmp / "proof.json"
    use_stub(wall, f'printf \'{{"proof_ref":"{proof}"}}\' > {{checkpoint}}; touch {proof}; exit 0')
    sup.tick(HEALTHY)
    launcher.wait_all()
    clock.t += 120
    sup.tick(HEALTHY)
    assert row(wall, "MUSE-01")["task_id"] == ""
    clock.t += wall.RESTART_BACKOFF + 1
    sup.tick(HEALTHY)
    assert row(wall, "MUSE-01")["task_id"] not in ("", "T1")
    launcher.wait_all()


def test_duplicate_start_is_prevented(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, "sleep 2")
    sup.tick(HEALTHY)
    rows = wall.load_state()
    for r in rows:  # simulate lost state: supervisor thinks slot is idle
        if r["slot_id"] == "MUSE-01": r["state"] = "IDLE"
    wall.save_state(rows)
    sup.tick(HEALTHY)
    assert launcher.starts.count("MUSE-01") == 1
    assert row(wall, "MUSE-01")["state"] == "WORKING"
    assert wall.acquire_lock() is not None and wall.acquire_lock() is None
    launcher.wait_all()


def test_fast_crashes_back_off_then_pause(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, "exit 3")
    delays = []
    for _ in range(wall.CRASH_LIMIT):
        sup.tick(HEALTHY)
        launcher.wait_all()
        clock.t += 1
        sup.tick(HEALTHY)
        r = row(wall, "MUSE-01")
        if r["state"] == "BACKOFF":
            delays.append(float(r["backoff_until"]) - clock.t)
            clock.t = float(r["backoff_until"]) + 0.1
    r = row(wall, "MUSE-01")
    assert r["state"] == "PAUSED_ERROR" and r["crash_count"] == str(wall.CRASH_LIMIT)
    assert delays == sorted(delays) and delays[0] >= wall.CRASH_BACKOFF_BASE - 1 and len(set(delays)) > 1
    starts = launcher.starts.count("MUSE-01")
    clock.t += 10_000
    sup.tick(HEALTHY)
    assert launcher.starts.count("MUSE-01") == starts  # paused stays paused
    assert wall.cmd_resume("MUSE-01") == 0 and row(wall, "MUSE-01")["state"] == "IDLE"


def test_rate_limit_exit_is_not_a_crash(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, f"exit {wall.RATE_LIMIT_EXIT}")
    sup.tick(HEALTHY)
    launcher.wait_all()
    clock.t += 1
    sup.tick(HEALTHY)
    r = row(wall, "MUSE-01")
    assert r["state"] == "RATE_LIMITED" and r["crash_count"] in ("", "0")


def test_resource_pressure_blocks_scale_up_and_kills_nothing(env):
    wall, launcher, clock, _ = env
    gov = wall.CapacityGovernor(requested_max=32, start_capacity=1, clock=clock)
    wall.cmd_start(32, loop=False)
    sup = wall.Supervisor(launcher=launcher, governor=gov, clock=clock)
    use_stub(wall, "sleep 3")
    sup.tick(HEALTHY)
    assert launcher.starts == ["MUSE-01"]          # ramp starts at 1
    clock.t += wall.RAMP_HOLD_SECONDS + 1
    sup.tick(CRITICAL)
    assert launcher.starts == ["MUSE-01"]           # no new worker under pressure
    assert launcher.is_alive("MUSE-01", None)       # running worker untouched
    assert row(wall, "MUSE-02")["state"] == "RESOURCE_BLOCKED"
    sup.tick(None)                                  # unreadable metrics hold
    assert launcher.starts == ["MUSE-01"]
    clock.t += wall.RAMP_HOLD_SECONDS + 1
    sup.tick(HEALTHY)
    assert gov.admitted_capacity == 4 and len(launcher.starts) == 4   # 1 -> 4 ladder
    launcher.wait_all()


def test_stop_prevents_restart(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, "exit 0")
    sup.tick(HEALTHY)
    launcher.wait_all()
    wall.cmd_stop(launcher=launcher)
    clock.t += 120
    sup.tick(HEALTHY)
    assert {r["state"] for r in wall.load_state()} == {"STOPPED"}
    assert len(launcher.starts) == 4


def test_four_slots_run_independently(env):
    wall, launcher, clock, _ = env
    sup = supervisor(wall, launcher, clock, target=4)
    use_stub(wall, 'case {slot_id} in MUSE-02) exit 3;; *) exit 0;; esac')
    sup.tick(HEALTHY)
    rows = {r["slot_id"]: r for r in wall.load_state()}
    assert [rows[f"MUSE-0{i}"]["state"] for i in range(1, 5)] == ["WORKING"] * 4
    assert len({rows[f"MUSE-0{i}"]["task_id"] for i in range(1, 5)}) == 4   # distinct tasks
    assert rows["MUSE-05"]["state"] == "STOPPED"                             # beyond target
    launcher.wait_all()
    clock.t += 1
    sup.tick(HEALTHY)
    rows = {r["slot_id"]: r for r in wall.load_state()}
    assert rows["MUSE-02"]["crash_count"] == "1"
    assert all(rows[s]["crash_count"] == "0" for s in ("MUSE-01", "MUSE-03", "MUSE-04"))


def test_defaults_are_safe_and_targets_limited(env):
    wall, *_ = env
    assert wall.get_requested_max({"profile": "AUTO"}) == 4
    assert wall.cmd_start(73, loop=False) == 2
    assert wall.cmd_start(64, loop=False) == 2
    assert wall.cmd_start(64, allow_64=True, loop=False) == 0


def test_claim_passes_global_options_before_subcommand(env):
    wall, *_ = env
    assert wall.try_claim_task("MUSE-09")[0] == "T1"
