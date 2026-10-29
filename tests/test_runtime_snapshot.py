import subprocess
import sys

import pytest

from courier_runtime.ownership import OwnedProcess, Registry
from courier_runtime.snapshot import (FAILED, IDLE_READY, NEEDS_USER, OS_WAIT, PROBING, QUIET,
                                      SURFACE_CORRUPTED, WORKING, classify, collect)

NOW = 10_000.0


def session(alive=True, exit_code=None, last=NOW - 5, complete=False, owes=True, pending=None,
            os_blocked=False, surface_ok=True):
    return {"session_id": "s1", "workkey": "wk",
            "process": {"pid": 1, "create_time": 1.0, "alive": alive, "exit_code": exit_code},
            "progress": {"last_progress_at": last},
            "turn": {"complete": complete, "owes_work": owes},
            "permission": {"pending": pending, "os_blocked_operation": os_blocked},
            "surface_ok": surface_ok}


@pytest.mark.parametrize("kw, state", [
    ({}, WORKING),
    ({"last": NOW - 600}, QUIET),
    ({"complete": True, "owes": False, "last": NOW - 600}, IDLE_READY),
    ({"pending": "user"}, NEEDS_USER),
    ({"pending": "os", "os_blocked": True}, OS_WAIT),
    ({"surface_ok": False}, SURFACE_CORRUPTED),
    ({"alive": False, "exit_code": 1}, FAILED),
    ({"alive": False, "exit_code": None}, PROBING),
])
def test_runtime_evidence_decides_the_state(kw, state):
    assert classify(session(**kw), NOW)["state"] == state


def test_os_dialog_that_blocks_nothing_is_not_a_wait():
    # 2026-10-02 field case: the firewall dialog was visible but did not block the process.
    verdict = classify(session(pending="os", os_blocked=False), NOW, visual_hint="firewall_dialog_visible")
    assert verdict["state"] == WORKING and verdict["visual_hint"] == "firewall_dialog_visible"


@pytest.mark.parametrize("hint", ["permission_dialog_visible", "terminal_stopped_text", "spinner_visible"])
def test_visual_hint_alone_never_changes_the_state(hint):
    assert classify(session(), NOW, visual_hint=hint)["state"] == WORKING
    assert classify(session(alive=False, exit_code=None), NOW, visual_hint=hint)["state"] == PROBING


def test_failed_requires_positive_exit_evidence():
    assert classify(session(alive=False, exit_code=None, last=NOW - 9999), NOW)["state"] != FAILED


def test_collect_sees_only_owned_processes(tmp_path):
    reg = Registry(str(tmp_path / "owned.json"))
    mine = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        reg.add(OwnedProcess.capture(mine.pid, "wk-1", "test"))
        snap = collect(reg, {"s1": {"workkey": "wk-1", "last_progress_at": NOW},
                             "s2": {"workkey": "wk-unknown"}}, host_id="h1", trigger={"kind": "user_request"},
                       clock=lambda: NOW)
        by = {s["session_id"]: s for s in snap["sessions"]}
        assert by["s1"]["process"]["pid"] == mine.pid and by["s1"]["process"]["alive"]
        assert by["s2"]["process"] is None
        assert all(s["process"] is None or s["process"]["pid"] != foreign.pid for s in snap["sessions"])
        assert snap["level"] == 0 and "pixels" not in str(snap)
        assert classify(by["s2"], NOW)["state"] == PROBING
    finally:
        mine.kill(), foreign.kill(), mine.wait(), foreign.wait()


def test_later_dead_record_does_not_hide_a_live_owned_process(tmp_path):
    """Two owned processes, one workkey. The later record has exited.
    The snapshot must still report the earlier process as alive."""
    import psutil

    reg = Registry(str(tmp_path / "owned.json"))
    first = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    second = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        reg.add(OwnedProcess.capture(first.pid, "wk-1", "test"))
        reg.add(OwnedProcess.capture(second.pid, "wk-1", "test"))
        second.kill()
        second.wait()
        snap = collect(reg, {"s1": {"workkey": "wk-1", "exit_code": second.returncode}},
                       host_id="h1", trigger={"kind": "user_request"}, clock=lambda: NOW)
        proc = snap["sessions"][0]["process"]
        assert proc["alive"] is True
        assert proc["pid"] == first.pid
        assert psutil.Process(first.pid).is_running()
        assert proc["pid"] != second.pid
    finally:
        if first.poll() is None:
            first.kill()
            first.wait()
        if second.poll() is None:
            second.kill()
            second.wait()
