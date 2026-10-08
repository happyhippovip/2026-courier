import pytest
from courier_runtime.snapshot import (
    classify, collect,
    WORKING, QUIET, IDLE_READY, NEEDS_USER, OS_WAIT,
    SURFACE_CORRUPTED, TERMINAL_HOST_FAILED, FAILED, PROBING
)


NOW = 20_000.0


def make_session(alive=True, exit_code=None, last=NOW - 10, complete=False, owes=True,
                 pending=None, os_blocked=False, surface_ok=True, is_terminal_host=False):
    return {
        "session_id": "sess-edge",
        "workkey": "wk-edge",
        "is_terminal_host": is_terminal_host,
        "process": {"pid": 42, "create_time": 42.0, "alive": alive, "exit_code": exit_code},
        "progress": {"last_progress_at": last},
        "turn": {"complete": complete, "owes_work": owes},
        "permission": {"pending": pending, "os_blocked_operation": os_blocked},
        "surface_ok": surface_ok
    }


def test_terminal_host_failed_transition():
    s = make_session(alive=False, exit_code=137, is_terminal_host=True)
    res = classify(s, NOW)
    assert res["state"] == TERMINAL_HOST_FAILED
    assert res["action"] == "RECOVER"
    assert "exit_code=137" in res["evidence"]


def test_dead_process_turn_complete_no_work_owed():
    s = make_session(alive=False, exit_code=0, complete=True, owes=False)
    res = classify(s, NOW)
    assert res["state"] == IDLE_READY
    assert res["action"] == "NONE"


def test_surface_broken_while_progressing_action():
    s = make_session(alive=True, surface_ok=False, last=NOW - 10)
    res = classify(s, NOW)
    assert res["state"] == SURFACE_CORRUPTED
    assert res["action"] == "RECONNECT_SURFACE"


def test_quiet_budget_custom_threshold():
    # Progress was 50 seconds ago, standard budget is 120s (WORKING)
    s = make_session(alive=True, last=NOW - 50)
    assert classify(s, NOW, quiet_after_s=120)["state"] == WORKING
    # If quiet_after_s is set to 30s, this transitions to QUIET
    assert classify(s, NOW, quiet_after_s=30)["state"] == QUIET


def test_no_process_recorded_always_probes():
    raw_s = {
        "session_id": "sess-empty",
        "workkey": "wk-empty",
        "process": None,
        "progress": {"last_progress_at": None},
        "turn": {"complete": False, "owes_work": False},
        "permission": {"pending": None, "os_blocked_operation": False},
        "surface_ok": True
    }
    res = classify(raw_s, NOW)
    assert res["state"] == PROBING
    assert res["action"] == "PROBE"
