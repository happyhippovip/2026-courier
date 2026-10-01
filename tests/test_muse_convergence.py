"""Focused canonical runtime regressions. No real Muse/provider/Keychain calls."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "mac_worker"))
import muse_adapter as adapter
import runtime_state as runtime
from test_mac_worker_recovery import load_daemon, FakeServer, StopLoop, task, run, state_file

HEALTHY = {"swap_mb": 0., "load_1m": .5, "mem_free_pct": 80.}
WORKSPACE = "/Users/user/Downloads/2026-courier"


class Launcher:
    def __init__(self): self.starts = []
    def start(self, slot, env): self.starts.append((slot, env)); return 100 + len(self.starts)
    def is_alive(self, slot, pid): return False
    def exit_code(self, slot): return 2


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    spec = importlib.util.spec_from_file_location("isolated_supervisor", ROOT / "scripts/mac_worker/muse_supervisor.py")
    sup = importlib.util.module_from_spec(spec); spec.loader.exec_module(sup)
    return sup


@pytest.mark.parametrize("metrics", [None, dict(HEALTHY, mem_free_pct=5.)])
def test_A_M_32_missing_or_unsafe_metrics_no_replacements(control, metrics):
    s = control
    assert s.cmd_start(32, loop=False) == 0
    governor = s.CapacityGovernor(32); governor.admitted = 32
    launcher = Launcher()
    s.Supervisor(launcher, governor).tick(metrics)
    assert launcher.starts == []
    assert len(s.load_slots()) == 32


def test_B_STOP_during_metric_read_prevents_spawn(control):
    s = control; s.cmd_start(1, loop=False)
    def metrics():
        s.cmd_stop()
        return HEALTHY
    launcher = Launcher()
    s.Supervisor(launcher, s.CapacityGovernor(1, reader=metrics)).tick()
    assert launcher.starts == []


def test_C_K_duplicate_start_cannot_clear_STOP_or_mutate_slots(control):
    s = control; s.cmd_start(1, loop=False); s.cmd_stop()
    before = s.SLOTS_FILE.read_bytes()
    lock = s.acquire_lock()
    try:
        assert s.cmd_start(32, loop=False) == 1
        assert s.STOP_FILE.exists()
        assert s.SLOTS_FILE.read_bytes() == before
        assert s.acquire_lock() is None
    finally:
        lock.close()
    assert s.cmd_start(1, loop=False) == 1  # ordinary start never clears STOP
    assert s.cmd_resume("all") == 0
    assert s.cmd_start(1, loop=False) == 0


@pytest.mark.parametrize("target", [1, 4, 8, 16, 32])
def test_L_start_target_and_workspace_persisted(control, target):
    s = control; assert s.cmd_start(target, loop=False) == 0
    assert len(s.load_slots()) == target
    assert all(v["workspace"] == WORKSPACE for v in s.load_slots().values())
    launch = Launcher(); s.Supervisor(launch).tick(HEALTHY)
    assert len(launch.starts) == 1
    assert launch.starts[0][1]["COURIER_MUSE_WORKSPACE"] == WORKSPACE


def test_D_worker_STOP_before_claim(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path))
    (tmp_path / "STOP").write_text("stop")
    server = FakeServer(); monkeypatch.setattr(daemon, "http_post", server)
    daemon.loop()
    assert server.posted("/tasks/claim") == []


def test_E_explicit_exec_workspace_from_wrong_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    argv, stdin = adapter.build_muse_command(task(), {}, {"protocol": "headless-v1"},
        slot_id="01", workspace=WORKSPACE)
    assert argv[:4] == ["muse", "exec", "--workspace", WORKSPACE]
    assert "dispatch-abc" in argv[-1] and stdin is None


def bound_checkpoint():
    return {"binding": adapter.task_binding(task(), "01", WORKSPACE),
            "session_ref": "provider-session-1", "session_ref_verified": True}


@pytest.mark.parametrize("action", ["resume", "session-message"])
def test_F_session_ref_persists_and_binds(tmp_path, action):
    result = adapter.parse_result(json.dumps({"session_ref": "provider-session-1", "result": {"status": "SUCCESS"}}),
                                  0, {"session_ref_format": "json-envelope-v1"})
    adapter.save_checkpoint(tmp_path, task(), result, slot_id="01", workspace=WORKSPACE)
    stored = adapter.load_checkpoint(tmp_path)
    argv, _ = adapter.build_muse_command(task(), stored,
        {"protocol": "headless-v1", "session_ref_format": "json-envelope-v1"},
        slot_id="01", workspace=WORKSPACE, action=action)
    assert argv[:5] == ["muse", action, "--workspace", WORKSPACE, "provider-session-1"]


@pytest.mark.parametrize("field", ["goal_id", "task_id", "attempt_id", "dispatch_id", "slot_id", "workspace"])
def test_G_foreign_checkpoint_never_resumed(field):
    checkpoint = bound_checkpoint(); checkpoint["binding"][field] = "foreign"
    with pytest.raises(adapter.MuseBindingError):
        adapter.build_muse_command(task(), checkpoint,
            {"protocol": "headless-v1", "session_ref_format": "json-envelope-v1"},
            slot_id="01", workspace=WORKSPACE, action="resume")


def test_unverified_model_session_is_not_resume_authority():
    parsed = adapter.parse_result('```json\n{"status":"SUCCESS","session_ref":"invented"}\n```', 0)
    assert "session_ref" not in parsed
    with pytest.raises(adapter.MuseBindingError):
        adapter.build_muse_command(task(), bound_checkpoint(), {"protocol": "headless-v1"},
            slot_id="01", workspace=WORKSPACE, action="resume")


def test_I_result_persistence_failure_no_send_no_next_claim(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], max_calls=12); executions = []
    persist = daemon.persist_task
    failures = []
    def disk_full(path, packet):
        if packet.get("worker_phase") == "RESULT_READY":
            failures.append(packet["result_payload"])
            raise OSError("synthetic ENOSPC")
        persist(path, packet)
    monkeypatch.setattr(daemon, "persist_task", disk_full)
    run(daemon, monkeypatch, server, executions)
    assert executions == ["task-1"]
    assert len(server.posted("/tasks/claim")) == 1
    assert server.posted("/tasks/result") == []
    assert len(failures) > 1 and all(p == failures[0] for p in failures)
    assert json.loads(state_file(daemon).read_text())["worker_phase"] == "STARTED"


def test_result_persistence_recovery_resends_same_result(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task()], results=[({"status": "ACK"}, None)])
    persist = daemon.persist_task; attempts = []
    def fail_once(path, packet):
        if packet.get("worker_phase") == "RESULT_READY":
            attempts.append(packet["result_payload"])
            if len(attempts) == 1: raise OSError("synthetic transient disk error")
        persist(path, packet)
    monkeypatch.setattr(daemon, "persist_task", fail_once)
    executions = []; run(daemon, monkeypatch, server, executions)
    assert executions == ["task-1"]
    assert attempts[0] == attempts[1] == server.posted("/tasks/result")[0]


def test_prompt_is_durable_and_reused(tmp_path):
    binding = adapter.task_binding(task(), "01", WORKSPACE)
    first = adapter.prepare_prompt(tmp_path, task(), binding, {}, {})
    second = adapter.prepare_prompt(tmp_path, task(instruction="changed"), binding, {}, {})
    assert first == second
    assert json.loads((tmp_path / "prompt.json").read_text())["binding"] == binding


def test_corrupt_state_fails_closed(control):
    s = control; s.cmd_start(1, loop=False); s.SLOTS_FILE.write_text("{broken")
    launcher = Launcher()
    with pytest.raises(ValueError): s.Supervisor(launcher).tick(HEALTHY)
    assert launcher.starts == []


def test_spawn_crash_is_not_blindly_restarted(control, monkeypatch):
    s = control; s.cmd_start(1, loop=False)
    class CrashingLauncher(Launcher):
        def start(self, slot, env):
            super().start(slot, env)
            raise RuntimeError("crash after spawning, before PID commit")
    launcher = CrashingLauncher()
    with pytest.raises(RuntimeError): s.Supervisor(launcher).tick(HEALTHY)
    fresh = Launcher(); s.Supervisor(fresh).tick(HEALTHY)
    assert not fresh.starts and s.load_slots()["01"]["state"] == "PAUSED_ERROR"


def test_PID_reuse_never_authorizes_kill(monkeypatch):
    class Proc:
        pid = 42
        def poll(self): return None
    monkeypatch.setattr(runtime, "process_identity", lambda pid: {"pid": 42, "pgid": 42, "fingerprint": "new"})
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: pytest.fail("unrelated process signalled"))
    assert not runtime.cleanup_group(Proc(), {"pid": 42, "pgid": 42, "fingerprint": "old"})


def test_unknown_interval_is_not_healthy_ramp_time(control):
    clock = [0.]
    gov = control.CapacityGovernor(32, clock=lambda: clock[0])
    assert gov.evaluate(None) == 0
    clock[0] = 10000.
    assert gov.evaluate(HEALTHY) == 1


@pytest.mark.parametrize("metrics", [{}, dict(HEALTHY, load_1m=float("nan")), dict(HEALTHY, swap_mb="unknown")])
def test_malformed_metrics_fail_closed(control, metrics):
    gov = control.CapacityGovernor(32); gov.admitted = 32
    assert gov.evaluate(metrics) == 0


def test_orphan_blocks_worker_before_claim(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    runtime.atomic_json(daemon.STATE_DIR / "muse_process.json", {"state": "STARTING"})
    server = FakeServer(); monkeypatch.setattr(daemon, "http_post", server)
    with pytest.raises(RuntimeError, match="Unreconciled"):
        daemon.loop()
    assert server.calls == []


def test_child_cleanup_TERM_then_KILL_only_owned_group(monkeypatch):
    identity = {"pid": 42, "pgid": 42, "fingerprint": "owned"}
    class Proc:
        pid = 42
        def poll(self): return None
    signals = []
    monkeypatch.setattr(runtime, "process_identity", lambda pid: identity)
    monkeypatch.setattr(runtime, "group_exists", lambda pid: len(signals) < 2)
    monkeypatch.setattr(runtime.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    assert runtime.cleanup_group(Proc(), identity, grace=0)
    assert signals == [(42, runtime.signal.SIGTERM), (42, runtime.signal.SIGKILL)]


def test_canary_exactly_once_no_queue_or_keychain(control, monkeypatch):
    import daemon
    s = control; calls = []
    monkeypatch.setattr(s, "read_macos_metrics", lambda: HEALTHY)
    monkeypatch.setattr(daemon, "load_config", lambda: pytest.fail("canary must not access Keychain/config"))
    monkeypatch.setattr(daemon, "http_post", lambda *a: pytest.fail("canary must not contact task queue"))
    def execute(packet, config):
        calls.append((packet, config))
        assert daemon.os.environ["COURIER_MUSE_WORKSPACE"] == WORKSPACE
        return {"status": "SUCCESS", "execution_mode": "MUSE"}
    monkeypatch.setattr(daemon, "run_muse", execute)
    assert s.cmd_canary() == 0
    assert s.cmd_canary() == 0
    assert len(calls) == 1 and calls[0][1]["MUSE_TIMEOUT_SECONDS"] == 60


def test_canary_ambiguous_started_never_replayed(control, monkeypatch):
    import daemon
    s = control
    monkeypatch.setattr(s, "read_macos_metrics", lambda: HEALTHY)
    def crash(*args): raise RuntimeError("execution may have occurred")
    monkeypatch.setattr(daemon, "run_muse", crash)
    with pytest.raises(RuntimeError): s.cmd_canary()
    monkeypatch.setattr(daemon, "run_muse", lambda *args: pytest.fail("canary replay"))
    assert s.cmd_canary() == 1


def test_canary_STOP_is_authoritative(control, monkeypatch):
    import daemon
    s = control; s.cmd_stop()
    monkeypatch.setattr(daemon, "run_muse", lambda *args: pytest.fail("canary spawned after STOP"))
    assert s.cmd_canary() == 1


def test_checkpoint_persistence_failure_retains_same_result(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task(mode="MUSE")], results=[({"status": "ACK"}, None)])
    executions = []; checkpoints = []
    def execute(packet, config):
        executions.append(packet["task_id"])
        return {"status": "FAILED", "execution_mode": "MUSE"}
    def checkpoint(*args, **kwargs):
        checkpoints.append(args[2])
        if len(checkpoints) == 1: raise OSError("synthetic checkpoint storage failure")
    monkeypatch.setattr(daemon, "run_muse", execute)
    monkeypatch.setattr(adapter, "save_checkpoint", checkpoint)
    run(daemon, monkeypatch, server, executions)
    assert executions == ["task-1"]
    assert len(checkpoints) == 2 and checkpoints[0] == checkpoints[1]
    assert len(server.posted("/tasks/result")) == 1


def test_storage_error_during_execution_blocks_further_claims(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    server = FakeServer(claims=[task(mode="MUSE")]); executions = []; sleeps = []
    def execute(*args):
        executions.append(1)
        raise OSError("execution output/checkpoint storage failed")
    def wait(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3: raise StopLoop()
    monkeypatch.setattr(daemon, "run_muse", execute)
    monkeypatch.setattr(daemon.time, "sleep", wait)
    run(daemon, monkeypatch, server, executions)
    assert executions == [1]
    assert len(server.posted("/tasks/claim")) == 1
    assert server.posted("/tasks/result") == []
    assert json.loads(state_file(daemon).read_text())["worker_phase"] == "RECOVERY_BLOCKED"


def test_legacy_unbound_Muse_claim_is_not_executed(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    state_file(daemon).write_text(json.dumps(task(mode="MUSE", worker_phase="CLAIMED")))
    monkeypatch.setattr(daemon, "run_muse", lambda *args: pytest.fail("unbound claim executed"))
    with pytest.raises(RuntimeError, match="Legacy unbound"):
        daemon.loop()


def test_real_owned_process_group_cleanup(tmp_path):
    """Only a synthetic Python child; no Muse, provider, shell or user processes."""
    import subprocess
    proc = subprocess.Popen([sys.executable, "-c",
        "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "print('ready',flush=True); time.sleep(30)"],
        start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    identity = None
    try:
        assert proc.stdout.readline().strip() == "ready"
        identity = runtime.process_identity(proc.pid)
        assert identity and identity["pgid"] == proc.pid
        assert runtime.cleanup_group(proc, identity, grace=.2)
        assert proc.poll() is not None
        assert not runtime.group_exists(proc.pid)
    finally:
        if identity and runtime.same_process(proc.pid, identity):
            runtime.cleanup_group(proc, identity)
        proc.stdout.close()
