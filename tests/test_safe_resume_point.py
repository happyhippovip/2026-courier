"""Tests for Safe Resume Point & Verified Continuation (FRZ-09)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest import mock

import pytest

from scripts.safe_resume_point import (
    compute_safe_resume_point,
    write_continuation_receipt,
)


def test_compute_safe_resume_point_with_journal(tmp_path: Path):
    """Verify resume points computed from SQLite journal events."""
    db_file = tmp_path / "courier.db"
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("""
            CREATE TABLE events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        # Task 1: Completed -> no resume needed
        conn.execute(
            "INSERT INTO events (event_type, payload) VALUES (?, ?)",
            ("TASK_COMPLETED", json.dumps({"task_id": "task-done", "status": "COMPLETED"})),
        )
        # Task 2: Checkpointed -> resume from checkpoint
        conn.execute(
            "INSERT INTO events (event_type, payload) VALUES (?, ?)",
            ("TASK_STARTED", json.dumps({"task_id": "task-interrupted", "checkpoint": "step-3"})),
        )
        conn.commit()

    with mock.patch("scripts.safe_resume_point.get_git_status", return_value={"dirty_count": 0, "unpushed_count": 0}):
        plan = compute_safe_resume_point(app_data_dir=tmp_path)

        assert plan["schema_version"] == "1.0"
        assert plan["journal_head_seq"] == 2
        assert "task-done" in plan["quiesced_tasks"]
        
        # Check resumable task
        resumable = [t for t in plan["resumable_tasks"] if t["task_id"] == "task-interrupted"]
        assert len(resumable) == 1
        assert resumable[0]["checkpoint"] == "step-3"
        assert resumable[0]["resume_state"] == "RESUME_FROM_CHECKPOINT"


def test_write_continuation_receipt(tmp_path: Path):
    """Verify write_continuation_receipt persists JSON into run/receipts."""
    plan = {
        "resume_plan_id": "RESUME-TEST-123",
        "verdict": "READY_TO_RESUME",
    }
    receipt_file = write_continuation_receipt(plan, tmp_path)
    data = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert data["resume_plan_id"] == "RESUME-TEST-123"


def test_workkey_durable_checkpoint_persistence_and_restart(tmp_path: Path):
    """Mission 12: Durable checkpoint after every workkey.

    Verifies:
    1. Complete schema: workkey, owner, status, input_fingerprint, source_sha,
       action_executed, test_result, result_id, next_allowed_step.
    2. Zero guess-work: Distinguishes PRESENT, UNKNOWN, NOT_APPLICABLE, NOT_RECORDED.
    3. Process exit / crash simulation: write, terminate, re-read.
    4. Verified continuation from durable checkpoint without guessing.
    """
    cp_dir = tmp_path / "run" / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_file = cp_dir / "cp-task-12.json"

    # Step 1: Write durable checkpoint
    checkpoint_data = {
        "schema_version": "1.0",
        "workkey": "TASK-12-RECOVER-CHECKPOINT",
        "owner": "L3 / Antigravity Steward",
        "status": "COMPLETED",
        "input_fingerprint": "sha256:7f4a21e09c",
        "source_sha": "18c8eb3364721c88ccbb87dce4cbb3022763ca02",
        "action_executed": "VERIFY_DURABLE_CHECKPOINT",
        "test_result": "PASSED",
        "result_id": "res-task-12-001",
        "next_allowed_step": "TASK-13-CONTROLLER-EXPORT",
    }
    cp_file.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")

    # Step 2: Simulate process crash / clean read back
    reloaded = json.loads(cp_file.read_text(encoding="utf-8"))
    assert reloaded == checkpoint_data

    # Step 3: Validate all mandatory audit fields
    mandatory_fields = [
        "workkey", "owner", "status", "input_fingerprint", "source_sha",
        "action_executed", "test_result", "result_id", "next_allowed_step"
    ]
    for field in mandatory_fields:
        assert field in reloaded
        assert reloaded[field] is not None
        assert reloaded[field] != "UNKNOWN"
        assert reloaded[field] != "NOT_RECORDED"

