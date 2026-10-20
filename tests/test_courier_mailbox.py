"""Tests for Courier Autonomous Mailbox Runner."""

import json
from pathlib import Path
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
    # Task remains untouched in inbox for later execution
    in_lines = inbox.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(in_lines[0])["status"] == "PENDING"
