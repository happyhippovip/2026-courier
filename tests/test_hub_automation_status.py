"""Hub automation card reads only <home>/ledger_bridge_state.json.

The file written by the ledger bridge is a mission map. It has no mission
status, blocker text, or per-mission timestamp. These tests pin the card to
that schema.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from courier_hub.automation_status import (
    MAX_STATE_BYTES,
    STALE_AFTER_SECONDS,
    automation_card,
)
from courier_hub.cli import main

T0 = datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc)
SECRET = "super-secret-bridge-token-should-not-leak"
MISSION = "mission-private-id-should-not-leak"


def _mission(**overrides):
    record = {
        "task_id": "task-a",
        "claim_event_id": "claim-a",
        "idempotency_key": "ledger:claim-a",
        "posted": True,
        "accepted_result_id": None,
        "attempt": 0,
        "spec_fingerprint": "fp",
        "source_sha": "a" * 40,
        "evidence_ref": "task_id=task-a;accepted_result_id=none;attempt=0",
    }
    record.update(overrides)
    return record


def _write(home, document, *, age_seconds):
    path = home / "ledger_bridge_state.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    stamp = (T0 - timedelta(seconds=age_seconds)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _assert_public(blob, home):
    text = blob if isinstance(blob, str) else json.dumps(blob)
    assert SECRET not in text
    assert MISSION not in text
    assert str(home) not in text
    assert "ledger_bridge_state.json" not in text
    assert "Traceback" not in text
    assert "HEALTHY" not in text
    assert "healthy" not in text
    assert "BLOCKED" not in text


def test_missing_file_is_not_configured(tmp_path):
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "NOT_CONFIGURED"
    assert card["label"] == "Not set up"
    assert card["in_flight"] is None
    assert card["record_age_seconds"] is None
    assert card["reason_code"] is None


def test_empty_missions_are_idle(tmp_path):
    _write(tmp_path, {"missions": {}}, age_seconds=30)
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "IDLE"
    assert card["label"] == "Idle"
    assert card["in_flight"] == 0
    assert card["record_age_seconds"] == 30
    assert "No missions are in flight." in card["detail"]


def test_settled_missions_are_idle(tmp_path):
    _write(
        tmp_path,
        {"missions": {"A": _mission(accepted_result_id="result-a"), "B": _mission(accepted_result_id="result-b")}},
        age_seconds=12,
    )
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "IDLE"
    assert card["in_flight"] == 0
    assert card["record_age_seconds"] == 12


def test_open_missions_are_running_with_record_age(tmp_path):
    _write(
        tmp_path,
        {
            "missions": {
                MISSION: _mission(evidence_ref=SECRET, idempotency_key=SECRET, task_id=SECRET, source_sha=SECRET),
                "done": _mission(accepted_result_id="result-done"),
                "claimed": _mission(posted=False, accepted_result_id=None),
            }
        },
        age_seconds=90,
    )
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "RUNNING"
    assert card["label"] == "Running"
    assert card["in_flight"] == 2
    assert card["record_age_seconds"] == 90
    assert card["detail"] == "2 missions have no accepted result. The record is 90 seconds old."
    assert card["reason_code"] is None


def test_one_open_mission_uses_singular_wording(tmp_path):
    _write(tmp_path, {"missions": {"A": _mission()}}, age_seconds=1)
    card = automation_card(tmp_path, T0)
    assert card["state"] == "RUNNING"
    assert card["in_flight"] == 1
    assert card["detail"] == "1 mission has no accepted result. The record is 1 second old."


def test_stale_open_missions_are_not_running(tmp_path):
    _write(tmp_path, {"missions": {MISSION: _mission(evidence_ref=SECRET)}}, age_seconds=STALE_AFTER_SECONDS + 1)
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "STALE"
    assert card["in_flight"] is None
    assert card["record_age_seconds"] == STALE_AFTER_SECONDS + 1
    assert card["detail"] == "The automation record is too old to say whether work is still moving."
    assert "RUNNING" not in card["detail"]


def test_stale_empty_record_stays_idle(tmp_path):
    _write(tmp_path, {"missions": {}}, age_seconds=STALE_AFTER_SECONDS + 5)
    card = automation_card(tmp_path, T0)
    assert card["state"] == "IDLE"
    assert card["in_flight"] == 0
    assert card["record_age_seconds"] == STALE_AFTER_SECONDS + 5


def test_boundary_age_is_still_running(tmp_path):
    _write(tmp_path, {"missions": {"A": _mission()}}, age_seconds=STALE_AFTER_SECONDS)
    card = automation_card(tmp_path, T0)
    assert card["state"] == "RUNNING"
    assert card["record_age_seconds"] == STALE_AFTER_SECONDS


def test_future_timestamp_is_attention(tmp_path):
    path = tmp_path / "ledger_bridge_state.json"
    path.write_text(json.dumps({"missions": {"A": _mission()}}), encoding="utf-8")
    stamp = (T0 + timedelta(seconds=300)).timestamp()
    os.utime(path, (stamp, stamp))
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "CLOCK"
    assert card["in_flight"] is None
    assert card["record_age_seconds"] is None
    assert "trust" in card["detail"]


def test_corrupt_file_is_attention_without_traceback(tmp_path, capsys):
    (tmp_path / "ledger_bridge_state.json").write_text("{not-json " + SECRET, encoding="utf-8")
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "UNREADABLE"
    assert card["detail"] == "The automation record could not be read."
    code = main(["courier-hub", "automation-status", "--home", str(tmp_path), "--now", T0.isoformat()])
    captured = capsys.readouterr()
    assert code == 0
    _assert_public(captured.out + captured.err, tmp_path)
    assert json.loads(captured.out)["state"] == "ATTENTION"


def test_malformed_shape_is_attention(tmp_path):
    _write(tmp_path, {"missions": []}, age_seconds=5)
    assert automation_card(tmp_path, T0)["reason_code"] == "MALFORMED"
    _write(tmp_path, {"missions": {}, "extra": SECRET}, age_seconds=5)
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "MALFORMED"
    _write(tmp_path, {"missions": {MISSION: {"task_id": 1}}}, age_seconds=5)
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["reason_code"] == "MALFORMED"


def test_oversized_file_is_not_read_past_the_cap(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    target = tmp_path / "ledger_bridge_state.json"
    with target.open("wb") as handle:
        handle.truncate(MAX_STATE_BYTES + (8 * 1024 * 1024))
    read_bytes = {"n": 0}
    real_open = Path.open

    def wrapped(self, mode="r", *args, **kwargs):
        handle = real_open(self, mode, *args, **kwargs)
        original = handle.read

        def read(n=-1):
            if n is None or n < 0 or n > MAX_STATE_BYTES + 1:
                raise AssertionError(f"read beyond cap: {n}")
            data = original(n)
            size = len(data.encode("utf-8")) if isinstance(data, str) else len(data)
            read_bytes["n"] += size
            if read_bytes["n"] > MAX_STATE_BYTES + 1:
                raise AssertionError(f"loaded {read_bytes['n']} bytes")
            return data

        handle.read = read
        return handle

    monkeypatch.setattr(Path, "open", wrapped)
    card = automation_card(tmp_path, T0)
    _assert_public(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "UNREADABLE"
    assert read_bytes["n"] <= MAX_STATE_BYTES + 1
    code = main(["courier-hub", "automation-status", "--home", str(tmp_path), "--now", T0.isoformat()])
    captured = capsys.readouterr()
    assert code == 0
    _assert_public(captured.out + captured.err, tmp_path)
    assert json.loads(captured.out)["reason_code"] == "UNREADABLE"


def test_cli_prints_one_card_and_hides_the_home_path(tmp_path, capsys):
    _write(tmp_path, {"missions": {MISSION: _mission(evidence_ref=SECRET)}}, age_seconds=4)
    code = main(["courier-hub", "automation-status", "--home", str(tmp_path), "--now", T0.isoformat()])
    captured = capsys.readouterr()
    assert code == 0
    _assert_public(captured.out + captured.err, tmp_path)
    card = json.loads(captured.out)
    assert card["state"] == "RUNNING"
    assert card["in_flight"] == 1
    assert card["record_age_seconds"] == 4
    assert list(card) == sorted(card)


def test_bad_now_does_not_echo_the_argument(tmp_path, capsys):
    _write(tmp_path, {"missions": {}}, age_seconds=1)
    leaked = str(tmp_path / "not-a-time")
    code = main(["courier-hub", "automation-status", "--home", str(tmp_path), "--now", leaked])
    captured = capsys.readouterr()
    assert code == 0
    assert leaked not in captured.out
    assert leaked not in captured.err
    assert "Traceback" not in captured.err
    assert json.loads(captured.out)["state"] == "ATTENTION"


def _z(age_seconds):
    return (T0 - timedelta(seconds=age_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_no_leak(blob, home):
    text = blob if isinstance(blob, str) else json.dumps(blob)
    assert SECRET not in text
    assert str(home) not in text
    assert "ledger_bridge_state.json" not in text
    assert "Traceback" not in text
    assert "healthy" not in text.lower()


def test_error_beats_blocked_and_posted(tmp_path):
    _write(
        tmp_path,
        {
            "missions": {
                "m-err": _mission(status="ERROR", reason="FAILED", updated_at=_z(5), evidence_ref=SECRET),
                "m-block": _mission(status="BLOCKED", reason="CONTROLLER_BLOCKED", updated_at=_z(5)),
                "m-run": _mission(status="POSTED", reason=None, updated_at=_z(5)),
            }
        },
        age_seconds=5,
    )
    card = automation_card(tmp_path, T0)
    _assert_no_leak(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "ERROR"
    assert card["reason_codes"] == ["FAILED"]
    assert card["mission_ids"] is None
    assert "m-block" not in json.dumps(card)
    assert card["detail"] == "1 mission ended in error. Reasons: FAILED."


def test_blocked_shows_count_reason_codes_and_at_most_five_ids(tmp_path):
    missions = {}
    for index in range(1, 7):
        missions[f"m-{index}"] = _mission(
            status="BLOCKED",
            reason="GOAL_PAIR" if index == 6 else "CONTROLLER_BLOCKED",
            updated_at=_z(8),
            task_id=SECRET,
        )
    missions["m-done"] = _mission(status="FINAL_DONE", reason=None, accepted_result_id="result-done", updated_at=_z(8))
    _write(tmp_path, {"missions": missions}, age_seconds=8)
    card = automation_card(tmp_path, T0)
    _assert_no_leak(card, tmp_path)
    assert card["state"] == "BLOCKED"
    assert card["label"] == "Blocked"
    assert card["blocked_count"] == 6
    assert card["in_flight"] is None
    assert card["reason_codes"] == ["CONTROLLER_BLOCKED", "GOAL_PAIR"]
    assert card["mission_ids"] == ["m-1", "m-2", "m-3", "m-4", "m-5"]
    assert card["detail"] == (
        "6 missions are blocked. Reasons: CONTROLLER_BLOCKED, GOAL_PAIR. "
        "Missions: m-1, m-2, m-3, m-4, m-5."
    )


def test_blocked_reason_null_omits_reason_list(tmp_path):
    _write(
        tmp_path,
        {"missions": {"m-1": _mission(status="BLOCKED", reason=None, updated_at=_z(4))}},
        age_seconds=4,
    )
    card = automation_card(tmp_path, T0)
    assert card["state"] == "BLOCKED"
    assert card["blocked_count"] == 1
    assert card["reason_codes"] == []
    assert card["mission_ids"] == ["m-1"]
    assert card["detail"] == "1 mission is blocked. Missions: m-1."


def test_posted_runs_and_only_final_done_is_idle(tmp_path):
    _write(
        tmp_path,
        {
            "missions": {
                "open": _mission(status="POSTED", reason=None, accepted_result_id="result-still-open", updated_at=_z(15)),
                "done": _mission(status="FINAL_DONE", reason=None, accepted_result_id=None, updated_at=_z(4000)),
            }
        },
        age_seconds=3,
    )
    running = automation_card(tmp_path, T0)
    assert running["state"] == "RUNNING"
    assert running["in_flight"] == 1
    assert running["record_age_seconds"] == 15

    _write(
        tmp_path,
        {"missions": {"done": _mission(status="FINAL_DONE", reason=None, accepted_result_id=None, updated_at=_z(15))}},
        age_seconds=3,
    )
    idle = automation_card(tmp_path, T0)
    assert idle["state"] == "IDLE"
    assert idle["in_flight"] == 0
    assert idle["record_age_seconds"] == 15


def test_unknown_status_or_reason_fails_closed(tmp_path):
    leaked_status = "SECRET-STATUS"
    _write(
        tmp_path,
        {"missions": {"m-1": _mission(status=leaked_status, reason="FAILED", updated_at=_z(2))}},
        age_seconds=2,
    )
    card = automation_card(tmp_path, T0)
    _assert_no_leak(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "UNKNOWN"
    assert leaked_status not in json.dumps(card)

    _write(
        tmp_path,
        {"missions": {"m-1": _mission(status="BLOCKED", reason=SECRET, updated_at=_z(2))}},
        age_seconds=2,
    )
    card = automation_card(tmp_path, T0)
    _assert_no_leak(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "UNKNOWN"
    assert card["state"] != "BLOCKED"


def test_legacy_derives_result_as_done_and_posted_as_running(tmp_path):
    _write(tmp_path, {"missions": {"A": _mission(accepted_result_id="result-a")}}, age_seconds=12)
    assert automation_card(tmp_path, T0)["state"] == "IDLE"
    _write(tmp_path, {"missions": {"A": _mission(posted=True, accepted_result_id=None)}}, age_seconds=12)
    running = automation_card(tmp_path, T0)
    assert running["state"] == "RUNNING"
    assert running["in_flight"] == 1
    assert running["record_age_seconds"] == 12
    _write(tmp_path, {"missions": {"A": _mission(posted=False, accepted_result_id=None)}}, age_seconds=12)
    claimed = automation_card(tmp_path, T0)
    assert claimed["state"] == "RUNNING"
    assert claimed["in_flight"] == 1


def test_updated_at_ages_posted_work_and_a_future_time_is_attention(tmp_path):
    _write(
        tmp_path,
        {"missions": {"A": _mission(status="POSTED", reason=None, updated_at=_z(90))}},
        age_seconds=10,
    )
    fresh = automation_card(tmp_path, T0)
    assert fresh["state"] == "RUNNING"
    assert fresh["record_age_seconds"] == 90

    _write(
        tmp_path,
        {"missions": {"A": _mission(status="POSTED", reason=None, updated_at=_z(STALE_AFTER_SECONDS + 1))}},
        age_seconds=10,
    )
    stale = automation_card(tmp_path, T0)
    assert stale["state"] == "ATTENTION"
    assert stale["reason_code"] == "STALE"
    assert stale["record_age_seconds"] == STALE_AFTER_SECONDS + 1

    _write(
        tmp_path,
        {"missions": {"A": _mission(status="POSTED", reason=None, updated_at=_z(20))}},
        age_seconds=STALE_AFTER_SECONDS + 30,
    )
    held = automation_card(tmp_path, T0)
    assert held["state"] == "RUNNING"
    assert held["record_age_seconds"] == 20

    future = (T0 + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write(
        tmp_path,
        {"missions": {"A": _mission(status="FINAL_DONE", reason=None, updated_at=future)}},
        age_seconds=5,
    )
    card = automation_card(tmp_path, T0)
    _assert_no_leak(card, tmp_path)
    assert card["state"] == "ATTENTION"
    assert card["reason_code"] == "CLOCK"
    assert future not in json.dumps(card)
    assert "trust" in card["detail"]

    _write(
        tmp_path,
        {"missions": {"A": _mission(status="POSTED", reason=None, updated_at="not-a-time")}},
        age_seconds=5,
    )
    bad = automation_card(tmp_path, T0)
    assert bad["state"] == "ATTENTION"
    assert bad["reason_code"] == "MALFORMED"
    assert "not-a-time" not in json.dumps(bad)
