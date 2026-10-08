import pytest
from courier_runtime.snapshot import (
    classify,
    PROBING,
    TERMINAL_HOST_FAILED,
    FAILED,
    IDLE_READY,
    SURFACE_CORRUPTED,
    WORKING,
    QUIET,
    NEEDS_USER,
    OS_WAIT,
)

NOW = 5000.0


def test_classify_no_process_probing():
    session = {"session_id": "s1", "workkey": "wk1", "process": None}
    res = classify(session, NOW)
    assert res["state"] == PROBING
    assert res["action"] == "PROBE"
    assert "no owned process recorded" in res["evidence"]


def test_classify_terminal_host_failed():
    session = {
        "session_id": "s1",
        "workkey": "wk1",
        "is_terminal_host": True,
        "process": {"pid": 100, "create_time": 10.0, "alive": False, "exit_code": 127},
    }
    res = classify(session, NOW)
    assert res["state"] == TERMINAL_HOST_FAILED
    assert res["action"] == "RECOVER"
    assert "exit_code=127" in res["evidence"]


def test_classify_dead_process_turn_complete_idle_ready():
    session = {
        "session_id": "s1",
        "workkey": "wk1",
        "process": {"pid": 100, "create_time": 10.0, "alive": False, "exit_code": 0},
        "turn": {"complete": True, "owes_work": False},
    }
    res = classify(session, NOW)
    assert res["state"] == IDLE_READY
    assert res["action"] == "NONE"


def test_classify_surface_corrupted_while_progressing():
    session = {
        "session_id": "s1",
        "workkey": "wk1",
        "process": {"pid": 100, "create_time": 10.0, "alive": True, "exit_code": None},
        "permission": {"pending": None, "os_blocked_operation": False},
        "progress": {"last_progress_at": NOW - 10.0},
        "surface_ok": False,
        "turn": {"complete": False, "owes_work": True},
    }
    res = classify(session, NOW, quiet_after_s=60)
    assert res["state"] == SURFACE_CORRUPTED
    assert res["action"] == "RECONNECT_SURFACE"
