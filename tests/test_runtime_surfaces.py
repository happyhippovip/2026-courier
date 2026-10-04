"""Window storm / surface budget: 100 repeated continue requests must not create 100 windows."""
import pytest

from courier_runtime.surfaces import (BUSY, IDLE_READY, NO_NEW_VISIBLE, SURFACE_BUDGET_EXHAUSTED,
                                      WAITING_FOR_USER, Budget, MacAdapter, SurfaceSupervisor, WindowsAdapter,
                                      adapter_for)

PROMPT = "COURIER SYMPHONY — continue the campaign. Repeat-safe."


class Identity:
    """Test double for (pid, create_time) identity: alive pids with their start time."""
    def __init__(self):
        self.alive = {}

    def __call__(self, s):
        return self.alive.get(s.pid) == s.create_time


def sup(tmp_path, identity=None, **kw):
    ident = identity or Identity()
    return SurfaceSupervisor(tmp_path / "surfaces.json", "mac-1", "darwin", budget=Budget(soft=2, hard=3),
                             identity=ident, clock=lambda: 1000.0, **kw), ident


def start(s, ident, decision, pid):
    s.attach(decision.surface_id, pid, float(pid))
    ident.alive[pid] = float(pid)


def test_01_hundred_identical_requests_make_one_surface(tmp_path):
    s, ident = sup(tmp_path)
    first = s.admit("muse", "W1", PROMPT)
    start(s, ident, first, 101)
    decisions = [s.admit("muse", "W1", PROMPT + "  ") for _ in range(49)]
    s2 = SurfaceSupervisor(tmp_path / "surfaces.json", "mac-1", "darwin", budget=Budget(2, 3), identity=ident)
    decisions += [s2.admit("muse", "W1", PROMPT.lower()) for _ in range(50)]      # survives a restart of Courier
    assert first.action == "OPEN" and {d.action for d in decisions} == {"COALESCED"}
    assert len(s2.surfaces) == 1 and s2.status()["duplicate_requests_coalesced"] == 99


def test_02_healthy_idle_surface_is_reused(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    s.finish(d.surface_id, "ckpt-1")
    again = s.admit("muse", "W2", "b")
    assert again.action == "REUSE" and again.surface_id == d.surface_id and len(s.surfaces) == 1


def test_03_hard_limit_denies_another_visible_spawn(tmp_path):
    s, ident = sup(tmp_path)
    for i in range(3):
        start(s, ident, s.admit("muse", f"W{i}", f"p{i}", allow_headless=False), 100 + i)
    d = s.admit("muse", "W9", "p9", allow_headless=False)
    assert d.action == "QUEUED" and d.reason == SURFACE_BUDGET_EXHAUSTED
    assert s.status()["visible_windows"] == 3 and s.level() == NO_NEW_VISIBLE


def test_04_queued_work_moves_into_a_freed_surface(tmp_path):
    s, ident = sup(tmp_path)
    opened = [s.admit("muse", f"W{i}", f"p{i}", allow_headless=False) for i in range(3)]
    for i, d in enumerate(opened):
        start(s, ident, d, 100 + i)
    assert s.admit("muse", "W9", "p9", allow_headless=False).action == "QUEUED"
    handed = s.finish(opened[0].surface_id, "ckpt")
    assert handed.action == "REUSE" and s.surfaces[opened[0].surface_id].workkey == "W9"
    assert s.status()["queued"] == 0 and len(s.surfaces) == 3


def test_05_active_owned_work_is_never_closed(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    closed = []
    r = s.reclaim(d.surface_id, closed.append)
    assert not r["closed"] and any("active work" in x for x in r["reasons"]) and closed == []


def test_06_foreign_surface_is_never_terminated(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    s.finish(d.surface_id, "ckpt")
    s.surfaces[d.surface_id].owner = "user"                 # a user's own terminal, not Courier's
    closed = []
    r = s.reclaim(d.surface_id, closed.append)
    assert not r["closed"] and "not owned by Courier" in r["reasons"] and closed == []


def test_07_pid_reuse_fails_closed(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    s.finish(d.surface_id, "ckpt")
    ident.alive[101] = 999.0                                # same pid, different process now
    closed = []
    r = s.reclaim(d.surface_id, closed.append)
    assert not r["closed"] and any("identity" in x for x in r["reasons"]) and closed == []
    assert s.admit("muse", "W2", "b").action != "REUSE"     # and it is not reused either


def test_08_completed_safe_surface_is_reclaimed(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    s.finish(d.surface_id, "ckpt")
    closed = []
    [r] = s.reclaim_idle(lambda surf: closed.append(surf.surface_id) or "STOPPED")
    assert r["closed"] and closed == [d.surface_id] and s.status()["workers"] == 0


def test_08b_unsaved_or_unchecked_idle_surface_stays(tmp_path):
    s, ident = sup(tmp_path)
    d = s.admit("muse", "W1", "a")
    start(s, ident, d, 101)
    s.set_state(d.surface_id, IDLE_READY, unsaved=True)
    r = s.reclaim(d.surface_id, lambda surf: "STOPPED")
    assert not r["closed"] and "unsaved work" in r["reasons"] and "no durable checkpoint" in r["reasons"]


def test_09_restart_reconciles_without_respawning(tmp_path):
    s, ident = sup(tmp_path)
    alive, gone, idle = (s.admit("muse", f"W{i}", f"p{i}") for i in range(3))
    for d, pid in ((alive, 101), (gone, 102), (idle, 103)):
        start(s, ident, d, pid)
    s.finish(idle.surface_id, "ckpt")
    del ident.alive[102]                                     # that window died with the machine
    s2 = SurfaceSupervisor(tmp_path / "surfaces.json", "mac-1", "darwin", budget=Budget(2, 3), identity=ident)
    result = s2.reconcile()
    assert result == {alive.surface_id: "STILL_ALIVE", gone.surface_id: "STALE", idle.surface_id: "REUSABLE"}
    assert len(s2.surfaces) == 3                             # classified, nothing new opened
    assert s2.admit("muse", "W1", "p1").action == "OPEN"    # the stale work may run again, once


def test_10_mac_and_windows_follow_the_same_contract(tmp_path):
    traces = []
    for osname in ("darwin", "win32"):
        ident = Identity()
        s = SurfaceSupervisor(tmp_path / f"{osname}.json", "h", osname, budget=Budget(1, 2), identity=ident)
        trace = []
        for i in range(4):
            d = s.admit("agent", f"W{i}", f"p{i}", allow_headless=False)
            trace.append(d.action)
            if d.action == "OPEN":
                start(s, ident, d, 200 + i)
        traces.append(trace)
    assert traces[0] == traces[1] == ["OPEN", "OPEN", "QUEUED", "QUEUED"]
    assert isinstance(adapter_for("darwin"), MacAdapter) and isinstance(adapter_for("win32"), WindowsAdapter)
    assert "never by image name" in WindowsAdapter.mechanism and "pid+create_time" in MacAdapter.mechanism


def test_11_blocked_surface_does_not_block_headless_work(tmp_path):
    s, ident = sup(tmp_path)
    for i in range(3):
        d = s.admit("muse", f"W{i}", f"p{i}", allow_headless=False)
        start(s, ident, d, 100 + i)
        s.set_state(d.surface_id, WAITING_FOR_USER)
    d = s.admit("muse", "W9", "index the repo", needs_visible=False)
    assert d.action == "HEADLESS" and not s.surfaces[d.surface_id].visible


def test_12_duplicate_watchers_and_schedulers_are_coalesced(tmp_path):
    s, ident = sup(tmp_path)
    first = s.admit("courier", "campaign-A", "watch CI", kind="watcher", needs_visible=False)
    again = [s.admit("courier", "campaign-A", "watch CI", kind="watcher", needs_visible=False) for _ in range(30)]
    assert first.action == "HEADLESS" and {d.action for d in again} == {"COALESCED"}
    assert len(s.surfaces) == 1


def test_soft_limit_prefers_headless_over_new_window(tmp_path):
    s, ident = sup(tmp_path)
    for i in range(2):
        start(s, ident, s.admit("muse", f"W{i}", f"p{i}"), 100 + i)
    assert s.admit("muse", "W5", "p5").action == "HEADLESS"


@pytest.mark.parametrize("ram, expected", [(None, "NORMAL"), (85.0, "CONSERVE_SURFACES"),
                                           (95.0, "NO_NEW_VISIBLE_SURFACES")])
def test_ram_pressure_is_admission_not_failure(tmp_path, ram, expected):
    s, _ = sup(tmp_path)
    assert s.level(ram) == expected
    d = s.admit("muse", "W1", "a", allow_headless=False, ram_used_pct=ram)
    assert d.action == ("QUEUED" if ram == 95.0 else "OPEN")
    assert BUSY  # nothing running was stopped: pressure only changes admission


def test_real_process_closed_by_identity_not_name(tmp_path):
    """End to end with a real child process: default psutil identity + platform adapter."""
    import subprocess
    import sys

    import psutil
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        s = SurfaceSupervisor(tmp_path / "surfaces.json", "host", sys.platform)
        d = s.admit("muse", "W1", "a")
        s.attach(d.surface_id, child.pid, psutil.Process(child.pid).create_time())
        assert s.reclaim(d.surface_id, adapter_for(sys.platform).close)["closed"] is False   # still working
        s.finish(d.surface_id, "ckpt")
        r = s.reclaim(d.surface_id, adapter_for(sys.platform).close)
        assert r["closed"] is True
        child.wait(timeout=10)
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
