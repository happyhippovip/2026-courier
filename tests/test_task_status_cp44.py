"""Tests for CP-44 / CQ-44 / GB-STATUS-EXPLAINER-01: Task Status Explainer & Observable State.

Verifies:
1. SUBMITTED state is never projected as running or executed ("SUBMITTED ist nicht ausgeführt").
2. Missing or unverifiable data is strictly classified as UNKNOWN ("fehlende Daten sind UNKNOWN").
3. Full preservation of raw technical details, stack traces, and exit codes ("technische Details erhalten").
4. High duration never triggers alarms solely because of elapsed time ("keine Alarmmeldungen allein wegen Dauer").
5. Evidence generation containing ['state-projection', 'freshness', 'error-codes'].
"""

import pytest

from courier_core.task_status_explainer import (
    CanonicalTaskState,
    TaskStatusExplainer,
    TaskStatusProjection,
)


def test_submitted_state_is_never_projected_as_running_or_executed():
    """Tasks in SUBMITTED state are projected as unstarted intake entries, never as executing."""
    explainer = TaskStatusExplainer()

    event = {
        "task_id": "task-intake-101",
        "state": "SUBMITTED",
        "timestamp_iso": "2026-10-21T12:00:00Z",
    }

    proj = explainer.project_task_status(event)

    assert proj.canonical_state == CanonicalTaskState.SUBMITTED
    assert "unstarted" in proj.compact_status_line
    assert proj.is_alarm_triggered is False


def test_missing_data_is_projected_as_unknown():
    """Events missing state or timestamps are safely mapped to UNKNOWN without false certainty."""
    explainer = TaskStatusExplainer()

    event = {
        "task_id": "task-unverified-02",
        # missing state & timestamp
    }

    proj = explainer.project_task_status(event)

    assert proj.canonical_state == CanonicalTaskState.UNKNOWN
    assert proj.freshness_age_seconds is None
    assert proj.is_alarm_triggered is False


def test_technical_details_and_error_codes_preserved():
    """Raw stack traces, exit codes, and error identifiers are preserved completely in projection."""
    explainer = TaskStatusExplainer()

    event = {
        "task_id": "task-err-03",
        "state": "FAILED",
        "timestamp_iso": "2026-10-21T12:05:00Z",
        "reason": "Process exited with non-zero status",
        "error_code": "ERR_EXIT_CODE_137",
        "technical_details": {
            "exit_code": 137,
            "signal": "SIGKILL",
            "stderr_snippet": "Killed by OOM protector",
        },
    }

    proj = explainer.project_task_status(event)

    assert proj.canonical_state == CanonicalTaskState.FAILED
    assert proj.error_code == "ERR_EXIT_CODE_137"
    assert proj.is_alarm_triggered is True
    assert proj.raw_technical_details["exit_code"] == 137
    assert "OOM" in proj.raw_technical_details["stderr_snippet"]


def test_long_duration_does_not_trigger_false_alarm():
    """Long-running operations (e.g. 2 hours render) do not trigger false alarm popups without an explicit error."""
    explainer = TaskStatusExplainer()

    event = {
        "task_id": "task-long-render-04",
        "state": "RUNNING",
        "timestamp_iso": "2026-10-21T10:00:00Z",
        "duration_seconds": 7200.0,  # 2 hours
    }

    proj = explainer.project_task_status(event, now_iso="2026-10-21T12:00:00Z")

    assert proj.canonical_state == CanonicalTaskState.RUNNING
    # Absolute invariant: Elapsed duration does NOT trip error alarm
    assert proj.is_alarm_triggered is False
    assert "7200s elapsed" in proj.compact_status_line
    assert proj.freshness_age_seconds == 7200.0


def test_waiting_and_blocked_states():
    """WAITING and BLOCKED states clearly display underlying dependency or gate."""
    explainer = TaskStatusExplainer()

    wait_event = {
        "task_id": "task-wait-05",
        "state": "WAITING",
        "timestamp_iso": "2026-10-21T12:10:00Z",
        "reason": "Awaiting CPU worker slot",
    }
    wait_proj = explainer.project_task_status(wait_event)
    assert wait_proj.canonical_state == CanonicalTaskState.WAITING
    assert wait_proj.is_alarm_triggered is False

    block_event = {
        "task_id": "task-block-06",
        "state": "BLOCKED",
        "timestamp_iso": "2026-10-21T12:15:00Z",
        "reason": "Human approval gate required",
    }
    block_proj = explainer.project_task_status(block_event)
    assert block_proj.canonical_state == CanonicalTaskState.BLOCKED
    assert block_proj.is_alarm_triggered is False


def test_evidence_generation():
    """Validates required catalog evidence keys: ['state-projection', 'freshness', 'error-codes']."""
    explainer = TaskStatusExplainer()
    explainer.project_task_status({
        "task_id": "task-fail-demo",
        "state": "FAILED",
        "timestamp_iso": "2026-10-21T12:20:00Z",
        "error_code": "ERR_CONN_REFUSED",
    })

    evidence = explainer.generate_status_evidence()

    assert "state-projection" in evidence
    assert "freshness" in evidence
    assert "error-codes" in evidence

    assert evidence["state-projection"][0]["canonical_state"] == "FAILED"
    assert evidence["freshness"][0]["timestamp"] == "2026-10-21T12:20:00Z"
    assert evidence["error-codes"][0]["error_code"] == "ERR_CONN_REFUSED"
