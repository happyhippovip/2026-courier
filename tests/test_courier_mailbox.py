"""Tests for Courier Autonomous Mailbox Runner."""

import json
from pathlib import Path
from unittest import mock
from scripts.courier_mailbox import process_inbox, main


def test_mailbox_unreadable_line_is_not_dropped(tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "courier_home"
    original = "\n".join([
        json.dumps({
            "task_id": "mission-ok",
            "estimated_cost_eur": 0.0,
            "status": "PENDING",
        }),
        "{not-json",
        "",
    ])
    inbox.write_text(original, encoding="utf-8")

    results = process_inbox(inbox, outbox, home_path=home)

    assert results == []
    assert inbox.read_text(encoding="utf-8") == original
    assert not outbox.exists()


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

