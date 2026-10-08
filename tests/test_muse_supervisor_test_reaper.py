"""Regression: Muse supervisor tests must prove subprocess cleanup (WP005)."""
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("fcntl")

ROOT = Path(__file__).resolve().parents[1]
MAC = ROOT / "scripts" / "mac_worker"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rt():
    sys.path.insert(0, str(MAC))
    return _load("runtime_state_reaper", MAC / "runtime_state.py")


@pytest.fixture
def reaper_mod():
    sys.path.insert(0, str(MAC))
    return _load("supervisor_test_reaper", MAC / "supervisor_test_reaper.py")


SLEEPER = [sys.executable, "-c", "import time; time.sleep(120)"]


def test_capture_identity_without_ps(rt, monkeypatch):
    def hang(*args, **kwargs):
        time.sleep(10)
        return ""
    monkeypatch.setattr(rt.subprocess, "check_output", hang)
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        ident = rt.capture_process_identity(proc)
        assert ident is not None
        assert ident["captured_at_spawn"] is True
        assert ident["pgid"] == os.getpgid(proc.pid)
        assert rt.identity_matches(proc.pid, ident)
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_ps_timeout_still_signals_owned_session(rt, monkeypatch):
    """A ps timeout must not skip a live Popen this process started."""
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        ident = rt.capture_process_identity(proc)
        assert ident is not None
        real = rt.subprocess.check_output

        def timeout_identity(args, *a, **k):
            if isinstance(args, (list, tuple)) and "-p" in args:
                raise subprocess.TimeoutExpired(cmd=args, timeout=0.25)
            return real(args, *a, **k)

        monkeypatch.setattr(rt.subprocess, "check_output", timeout_identity)
        if sys.platform == "darwin":
            assert rt.fingerprints_match(proc.pid, ident) is False
        assert rt.cleanup_group(proc, ident) is True
        proc.wait(timeout=5)
    finally:
        if proc.returncode is None:
            proc.kill()
            proc.wait(timeout=5)


def test_pid_pgid_hash_does_not_override_ps_fingerprint(rt):
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        ident = rt.capture_process_identity(proc)
        assert ident is not None
        bare = rt._fingerprint(proc.pid, ident["pgid"])
        if sys.platform == "darwin":
            assert ident.get("ps_fingerprint")
            assert ident["fingerprint"] == ident["ps_fingerprint"]
            assert ident["fingerprint"] != bare
        mismatched = dict(ident)
        mismatched["fingerprint"] = bare
        mismatched["ps_fingerprint"] = "0" * 64
        assert rt.fingerprints_match(proc.pid, mismatched) is False
        assert rt.identity_matches(proc.pid, ident) is True
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_recovered_zombie_without_live_members_is_cleaned(rt, monkeypatch):
    class Recovered:
        def __init__(self):
            self.pid = 424242
            self.returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(rt, "_pid_liveness", lambda pid: "zombie")
    monkeypatch.setattr(rt, "_pgroup_has_live_members", lambda pgid: False)
    signals = {"n": 0}

    def refuse_killpg(pgid, sig):
        signals["n"] += 1
        raise PermissionError("zombie leader")

    monkeypatch.setattr(rt.os, "killpg", refuse_killpg)
    ident = {"pid": 424242, "pgid": 424242, "fingerprint": "abc", "source": "ps"}
    proc = Recovered()
    assert rt.cleanup_group(proc, ident, grace=0.01) is True
    assert signals["n"] == 0
    assert rt.process_group_stopped(proc, ident) is True


def test_group_ps_includes_ttyless_members(rt, monkeypatch):
    seen = {}
    real = rt.subprocess.check_output

    def wrapped(args, *a, **k):
        if isinstance(args, (list, tuple)) and "-g" in args:
            seen["args"] = list(args)
        return real(args, *a, **k)

    monkeypatch.setattr(rt.subprocess, "check_output", wrapped)
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        assert rt.group_exists(os.getpgid(proc.pid)) is True
    finally:
        proc.kill()
        proc.wait(timeout=5)
    if sys.platform == "darwin":
        assert "-x" in seen["args"]


def test_normal_termination_verified(reaper_mod):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(proc, "sleeper")
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    reaper.cleanup_all()


def _await_unreaped_dead(pid, timeout=2.0):
    """True when the child is dead and still unreaped.

    Darwin: kill(pid, 0) succeeds and getpgid returns ESRCH.
    Linux: the zombie still has a pgid; /proc state is Z.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        try:
            os.getpgid(pid)
        except ProcessLookupError:
            return True
        if sys.platform.startswith("linux"):
            try:
                stat = Path(f"/proc/{int(pid)}/stat").read_text()
            except OSError:
                return False
            end = stat.rfind(")")
            if end >= 0 and end + 2 < len(stat) and stat[end + 2] == "Z":
                return True
        time.sleep(0.01)
    return False


def test_dead_or_zombie_child_is_not_a_verified_termination(rt):
    """A dead child is not a live identity match.

    Darwin reports that child via kill(pid, 0) while getpgid returns ESRCH.
    Linux keeps the pgid until the parent reaps the zombie. A zombie leader
    with no live members is still a finished group, so cleanup is proven.
    """
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        ident = rt.capture_process_identity(proc)
        assert ident is not None
        os.kill(proc.pid, signal.SIGTERM)
        assert _await_unreaped_dead(proc.pid)
        assert proc.returncode is None
        assert rt.identity_matches(proc.pid, ident) is False
        if sys.platform == "darwin":
            os.kill(proc.pid, 0)
            with pytest.raises(ProcessLookupError):
                os.getpgid(proc.pid)
        assert rt.cleanup_identity_authority(proc.pid, ident) is True
        assert rt.cleanup_group(proc, ident) is True
        assert proc.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(proc.pid, 0)
    finally:
        if proc.returncode is None:
            proc.kill()
            proc.wait(timeout=5)


def test_forced_termination(reaper_mod):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(proc)
    reaper.cleanup_all()


def test_cleanup_after_exception_still_runs(reaper_mod):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(proc)
    try:
        raise ValueError("simulated test failure")
    except ValueError:
        reaper.cleanup_all()


def test_already_dead_is_success(reaper_mod):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, start_new_session=True)
    proc.wait(timeout=5)
    reaper.register(proc)
    reaper.cleanup_all()


def test_missing_identity_fails_closed(reaper_mod):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper._records.append(reaper_mod._Record(proc=proc, identity=None, label="no-ident"))
    with pytest.raises(RuntimeError, match="CLEANUP_NOT_PROVEN"):
        reaper.cleanup_all()
    proc.kill()
    proc.wait(timeout=5)


def test_failure_to_terminate_raises(reaper_mod, monkeypatch):
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(proc, "ignores-signals")
    monkeypatch.setattr(reaper_mod, "cleanup_group", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="CLEANUP_NOT_PROVEN"):
        reaper.cleanup_all()
    proc.kill()
    proc.wait(timeout=5)


def test_unrelated_process_not_killed(reaper_mod, rt):
    reaper = reaper_mod.SupervisorTestReaper()
    foreign = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    owned = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(owned, "owned")
    reaper.cleanup_all()
    assert foreign.poll() is None
    foreign.kill()
    foreign.wait(timeout=5)


def test_cleanup_verification_detects_live_orphan(reaper_mod, rt, tmp_path):
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    ident = rt.capture_process_identity(proc)
    slot = tmp_path / "slot"
    slot.mkdir()
    assert reaper_mod.detect_stale_slot_with_live_process(slot, str(proc.pid), ident)
    proc.kill()
    proc.wait(timeout=5)
    assert not reaper_mod.detect_stale_slot_with_live_process(slot, str(proc.pid), ident)


def test_launcher_b_terminates_group_spawned_by_launcher_a(rt):
    """F2: terminate using pgid+fingerprint, not launcher-local Popen handle."""
    sys.path.insert(0, str(MAC))
    sup = _load("muse_supervisor_reaper", MAC / "muse_supervisor.py")
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    launcher_a = sup.ProcessLauncher()
    launcher_a.children["01"] = proc
    launcher_a.identities["01"] = rt.capture_process_identity(proc)
    identity = launcher_a.identities["01"]
    launcher_b = sup.ProcessLauncher()
    assert launcher_b.terminate("01", proc.pid, identity)
    assert not rt.group_exists(identity["pgid"])
    proc.wait(timeout=5)


def test_identity_matches_false_when_recorded_pid_is_dead(rt):
    """N1: liveness checks must not treat a dead leader as still owned."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, start_new_session=True)
    ident = rt.capture_process_identity(proc)
    pid = proc.pid
    proc.wait(timeout=5)
    assert rt.identity_matches(pid, ident) is False
    assert rt.cleanup_identity_authority(pid, ident) is True


def test_identity_matches_rejects_fake_fingerprint_on_live_leader(rt):
    """F3: captured_at_spawn does not bypass fingerprint mismatch."""
    foreign = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        pgid = os.getpgid(foreign.pid)
        fake = {
            "pid": foreign.pid,
            "pgid": pgid,
            "fingerprint": "0" * 64,
            "captured_at_spawn": True,
            "spawn_recorded_at": time.time(),
        }
        assert rt.identity_matches(foreign.pid, fake) is False
    finally:
        foreign.kill()
        foreign.wait(timeout=5)


def test_cleanup_kills_child_that_ignores_sigterm(rt):
    """F6: SIGKILL after leader reaps while group still exists."""
    child = (
        "import signal,time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "time.sleep(120)\n"
    )
    cmd = f'{sys.executable} -c "{child}" & wait'
    proc = subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, start_new_session=True)
    identity = rt.capture_process_identity(proc)
    assert identity is not None
    assert rt.cleanup_group(proc, identity)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not rt.group_exists(identity["pgid"]):
            break
        time.sleep(0.05)
    assert not rt.group_exists(identity["pgid"])


def test_bounded_cleanup_no_infinite_retry(reaper_mod, monkeypatch):
    calls = {"n": 0}
    real_cleanup = reaper_mod.cleanup_group

    def counting(proc, identity, grace=0.05):
        calls["n"] += 1
        return real_cleanup(proc, identity, grace=0.01)

    monkeypatch.setattr(reaper_mod, "cleanup_group", counting)
    reaper = reaper_mod.SupervisorTestReaper()
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL, start_new_session=True)
    reaper.register(proc)
    reaper.cleanup_all()
    assert calls["n"] <= reaper_mod._MAX_CLEANUP_ROUNDS * 4
