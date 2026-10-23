"""Tests for Courier Autonomous Mailbox Runner."""

import json
from pathlib import Path
from unittest import mock
from scripts.courier_mailbox import process_inbox, main


def test_mailbox_processes_pending_task(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "courier_home"
    
    # Write one pending task
    task = {
        "task_id": "mission-01",
        "name": "Erste grüne Mission",
        "goal": "Deterministischer Prüflauf",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")
    
    # Process
    results = process_inbox(inbox, outbox, home_path=home)
    assert len(results) == 1
    
    # Check outbox
    out_lines = outbox.read_text(encoding="utf-8").strip().splitlines()
    assert len(out_lines) == 1
    receipt = json.loads(out_lines[0])
    assert receipt["task_id"] == "mission-01"
    assert receipt["execution_result"]["overall_status"] == "COMPLETE"
    assert receipt["execution_result"]["verifier_result"]["resolution"] == "verified"
    
    # Check updated inbox
    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    updated = json.loads(in_lines[0])
    assert updated["status"] == "DONE"
    assert updated["resolution"] == "verified"


def test_mailbox_costgate_blocks_paid_task(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    
    # Task with illegal cost > 0.0
    task = {
        "task_id": "mission-paid-unauth",
        "name": "Unautorisierte Bezahl-Aufgabe",
        "estimated_cost_eur": 12.50,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")
    
    results = process_inbox(inbox, outbox)
    assert len(results) == 0
    assert not outbox.exists()
    
    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    updated = json.loads(in_lines[0])
    assert updated["status"] == "BLOCKED_COSTGATE"
    assert updated["resolution"] == "COSTGATE_REJECTED"


def test_mailbox_bool_cost_is_not_one_euro(tmp_path):
    """True is not 1 euro. A bool estimate stays unknown and does not run."""
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "courier_home"
    task = {
        "task_id": "mission-bool-cost",
        "name": "Bool ist kein Euro",
        "estimated_cost_eur": True,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    updated = json.loads(inbox.read_text(encoding="utf-8").strip())
    assert results == []
    assert not outbox.exists()
    assert updated["status"] == "BLOCKED_COSTGATE"
    assert updated["resolution"] == "UNKNOWN_COST", updated["resolution"]
    false_task = dict(task, task_id="mission-bool-false", estimated_cost_eur=False)
    inbox.write_text(json.dumps(false_task) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    updated = json.loads(inbox.read_text(encoding="utf-8").strip())
    assert results == []
    assert not outbox.exists()
    assert updated["status"] == "BLOCKED_COSTGATE"
    assert updated["resolution"] == "UNKNOWN_COST"


def test_mailbox_resource_pause_blocks_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    pause_file = tmp_path / "dev-night" / "RESOURCE_PAUSE"
    pause_file.parent.mkdir(parents=True)
    pause_file.write_text("PAUSE")

    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    task = {
        "task_id": "mission-paused",
        "name": "Aufgabe während Pause",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")

    results = process_inbox(inbox, outbox)
    assert results == []
    assert not outbox.exists()
    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(in_lines[0])["status"] == "PENDING"


def test_mailbox_single_writer_lease_conflict_prevents_race(tmp_path):
    """Proves that a competing runner holding the mailbox lease aborts safely fail-closed."""
    from courier_runtime.lease import LeaseStore

    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "courier_home"
    home.mkdir(parents=True, exist_ok=True)

    task = {
        "task_id": "mission-compete",
        "name": "Konkurrierende Aufgabe",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")

    # Another runner holds the lease on this mailbox
    auth_db = home / "authority.db"
    store = LeaseStore(str(auth_db))
    held_lease = store.acquire(f"mailbox:{inbox.name}", "other_runner:9999", "external_lock", ttl_s=60)

    # process_inbox detects LeaseConflict and aborts without executing
    results = process_inbox(inbox, outbox, home_path=home)
    assert results == []
    assert not outbox.exists()

    # Once released, process_inbox succeeds
    store.release(held_lease)
    store.close()
    results = process_inbox(inbox, outbox, home_path=home)
    assert len(results) == 1
    assert outbox.exists()


def test_mailbox_costgate_blocks_missing_cost(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    task = {
        "task_id": "mission-no-cost",
        "name": "Aufgabe ohne Kostenschätzung",
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")

    results = process_inbox(inbox, outbox)
    assert len(results) == 0
    assert not outbox.exists()

    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    updated = json.loads(in_lines[0])
    assert updated["status"] == "BLOCKED_COSTGATE"
    assert updated["resolution"] == "UNKNOWN_COST"


def test_mailbox_unknown_mark_beside_zero_does_not_run(tmp_path, monkeypatch):
    """A zero next to an unknown mark is not an explicit free task."""
    calls = {"n": 0}

    def chip(**kwargs):
        calls["n"] += 1
        raise AssertionError("unknown cost must not run")

    monkeypatch.setattr("scripts.courier_mailbox.run_mission_chip", chip)
    bodies = [
        {"task_id": "mission-unknown", "estimated_cost_eur": 0.0, "unknown_cost": True},
        {"task_id": "mission-class", "estimated_cost_eur": 0.0, "cost_class": "unknown"},
        {"task_id": "mission-params-mark", "estimated_cost_eur": 0.0, "params": {"unknown_cost": True}},
        {
            "task_id": "mission-params-class",
            "params": {"estimated_cost_eur": 0.0, "cost_class": "unknown"},
        },
        {
            "task_id": "mission-disagree",
            "estimated_cost_eur": 0.0,
            "params": {"estimated_cost_eur": 99.0},
        },
        {"task_id": "mission-negative", "estimated_cost_eur": -1.0},
    ]
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    inbox.write_text(
        "\n".join(json.dumps(dict(body, status="PENDING")) for body in bodies) + "\n",
        encoding="utf-8",
    )
    results = process_inbox(inbox, outbox, home_path=home)
    rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line]
    assert results == []
    assert calls["n"] == 0
    assert not outbox.exists()
    assert [row["status"] for row in rows] == ["BLOCKED_COSTGATE"] * len(bodies)
    assert [row["resolution"] for row in rows] == ["UNKNOWN_COST"] * len(bodies)
    assert [row["reason"] for row in rows] == ["UNKNOWN_COST"] * len(bodies)


def test_mailbox_explicit_zero_still_runs(tmp_path, monkeypatch):
    calls = {"n": 0}

    def chip(**kwargs):
        calls["n"] += 1
        return {
            "overall_status": "COMPLETE",
            "verifier_result": {
                "accepted": True,
                "resolution": "verified",
                "accepted_result_id": "r-zero",
            },
        }

    monkeypatch.setattr("scripts.courier_mailbox.run_mission_chip", chip)
    lines = [
        {
            "task_id": "top-zero",
            "estimated_cost_eur": 0.0,
            "unknown_cost": False,
            "status": "PENDING",
        },
        {
            "task_id": "params-zero",
            "status": "PENDING",
            "params": {"estimated_cost_eur": 0.0},
        },
    ]
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    inbox.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line]
    assert calls["n"] == 2
    assert len(results) == 2
    assert [row["status"] for row in rows] == ["DONE", "DONE"]
    assert [row["resolution"] for row in rows] == ["verified", "verified"]


def test_mailbox_bool_task_id_does_not_execute(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    task = {
        "task_id": True,
        "name": "bool id",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    assert results == []
    updated = json.loads(inbox.read_text(encoding="utf-8").strip())
    assert updated["status"] == "BLOCKED"
    assert updated["resolution"] == "INVALID_TASK_ID"
    assert not outbox.exists()


def test_mailbox_non_string_task_id_does_not_execute(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    lines = []
    for raw_id in (7, "", {"n": 1}):
        lines.append(json.dumps({
            "task_id": raw_id,
            "name": "bad id",
            "estimated_cost_eur": 0.0,
            "status": "PENDING",
        }))
    inbox.write_text("\n".join(lines) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    assert results == []
    assert not outbox.exists()
    updated = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line]
    assert [row["resolution"] for row in updated] == ["INVALID_TASK_ID"] * 3
    assert [row["status"] for row in updated] == ["BLOCKED"] * 3


def test_failed_chip_is_not_marked_done(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    inbox.write_text(json.dumps({
        "task_id": "mission-fail",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr("scripts.courier_mailbox.run_mission_chip", lambda **kwargs: {
        "overall_status": "FAILED",
        "verifier_result": {"accepted": False, "resolution": None},
    })
    results = process_inbox(inbox, outbox, home_path=home)
    updated = json.loads(inbox.read_text(encoding="utf-8").strip())
    assert results == []
    assert not outbox.exists()
    assert updated["status"] == "FAILED"
    assert updated["resolution"] == "NOT_VERIFIED"


def test_missing_task_id_does_not_run(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    calls = {"n": 0}

    def chip(**kwargs):
        calls["n"] += 1
        raise AssertionError("blank id must not run")

    monkeypatch.setattr("scripts.courier_mailbox.run_mission_chip", chip)
    line = json.dumps({"estimated_cost_eur": 0.0, "status": "PENDING"})
    inbox.write_text(line + "\n" + line + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    rows = [json.loads(item) for item in inbox.read_text(encoding="utf-8").splitlines() if item]
    assert results == []
    assert calls["n"] == 0
    assert not outbox.exists()
    assert [row["status"] for row in rows] == ["BLOCKED", "BLOCKED"]
    assert [row["resolution"] for row in rows] == ["INVALID_TASK_ID", "INVALID_TASK_ID"]


def test_malformed_inbox_line_is_kept_and_does_not_run(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    monkeypatch.setattr(
        "scripts.courier_mailbox.run_mission_chip",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("malformed inbox must not run")),
    )
    raw = '{"task_id":"mission-ok","estimated_cost_eur":0.0,"status":"PENDING"}\n{not-json}\n'
    inbox.write_text(raw, encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    assert results == []
    assert inbox.read_text(encoding="utf-8") == raw
    assert not outbox.exists()


def test_mailbox_lease_store_failure_fails_closed(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    task = {
        "task_id": "mission-lease-fail",
        "name": "Aufgabe bei LeaseStore-Fehler",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n", encoding="utf-8")

    from courier_runtime import lease
    monkeypatch.setattr(lease.LeaseStore, "acquire", mock.MagicMock(side_effect=OSError("disk I/O error")))

    results = process_inbox(inbox, outbox)
    assert results == []
    assert not outbox.exists()
    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(in_lines[0])["status"] == "PENDING"

