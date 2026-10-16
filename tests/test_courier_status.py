"""Unit tests for scripts/courier_status.py (Headless Status L0, Reboot Verdict, FRZ-02/FRZ-07)."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.courier_status import (
    evaluate_reboot_verdict,
    format_status_report,
    get_critical_snapshot_l0,
    get_journal_stats,
    get_owned_pids,
)


@pytest.fixture(autouse=True)
def mock_clean_git(monkeypatch):
    monkeypatch.setattr("scripts.courier_status.get_git_status", lambda repo_dir=None: {
        "branch": "lane/L6-clean-machine-acceptance",
        "dirty_count": 0,
        "unpushed_count": 0,
        "clean": True,
    })


def test_courier_status_empty_home(tmp_path):
    snapshot = get_critical_snapshot_l0(tmp_path)
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["app_data_dir"] == str(tmp_path)
    assert snapshot["owned_processes"] == {}
    assert snapshot["active_claims"] == []
    assert not snapshot["journal"]["exists"]
    assert snapshot["reboot_verdict"]["safe"] is True
    assert snapshot["reboot_verdict"]["verdict"] == "SAFE_TO_REBOOT"


def test_courier_status_with_v1_journal(tmp_path):
    db_path = tmp_path / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT)")
    conn.execute("INSERT INTO events (seq, type) VALUES (1, 'TASK_CREATED')")
    conn.execute("INSERT INTO events (seq, type) VALUES (2, 'TASK_COMPLETE')")

    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.execute("INSERT INTO tasks (task_id, status) VALUES ('task-1', 'COMPLETE')")
    conn.execute("INSERT INTO tasks (task_id, status) VALUES ('task-2', 'COMPLETE')")
    conn.commit()
    conn.close()

    stats = get_journal_stats(tmp_path)
    assert stats["exists"] is True
    assert stats["event_count"] == 2
    assert stats["last_seq"] == 2
    assert stats["tasks"] == {"COMPLETE": 2}

    snapshot = get_critical_snapshot_l0(tmp_path)
    assert snapshot["journal"]["exists"] is True
    assert snapshot["journal"]["tasks"] == {"COMPLETE": 2}
    assert snapshot["reboot_verdict"]["safe"] is True


def test_courier_status_reboot_verdict_blocked_by_active_claims(tmp_path):
    claims_dir = tmp_path / "run" / "claims"
    claims_dir.mkdir(parents=True)
    claim_file = claims_dir / "dispatch-42.json"
    claim_file.write_text(json.dumps({"task_id": "task-42", "owner_pid": 9999}), encoding="utf-8")

    snapshot = get_critical_snapshot_l0(tmp_path)
    assert len(snapshot["active_claims"]) == 1
    assert snapshot["reboot_verdict"]["safe"] is False
    assert snapshot["reboot_verdict"]["verdict"] == "NOT_SAFE_TO_REBOOT"
    assert any("active task claims" in r for r in snapshot["reboot_verdict"]["reasons"])


def test_courier_status_reboot_verdict_blocked_by_running_task(tmp_path):
    db_path = tmp_path / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT)")
    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.execute("INSERT INTO tasks (task_id, status) VALUES ('task-live', 'RUNNING')")
    conn.commit()
    conn.close()

    snapshot = get_critical_snapshot_l0(tmp_path)
    assert snapshot["reboot_verdict"]["safe"] is False
    assert snapshot["reboot_verdict"]["verdict"] == "NOT_SAFE_TO_REBOOT"
    assert any("marked RUNNING" in r for r in snapshot["reboot_verdict"]["reasons"])


def test_courier_status_reboot_verdict_blocked_by_dirty_git(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.courier_status.get_git_status", lambda repo_dir=None: {
        "branch": "lane/L6-clean-machine-acceptance",
        "dirty_count": 5,
        "unpushed_count": 0,
        "clean": False,
    })
    snapshot = get_critical_snapshot_l0(tmp_path)
    assert snapshot["reboot_verdict"]["safe"] is False
    assert snapshot["reboot_verdict"]["verdict"] == "NOT_SAFE_TO_REBOOT"
    assert any("uncommitted modified files" in r for r in snapshot["reboot_verdict"]["reasons"])


def test_courier_status_reboot_verdict_blocked_by_unpushed_commits(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.courier_status.get_git_status", lambda repo_dir=None: {
        "branch": "lane/L6-clean-machine-acceptance",
        "dirty_count": 0,
        "unpushed_count": 71,
        "clean": True,
    })
    snapshot = get_critical_snapshot_l0(tmp_path)
    assert snapshot["reboot_verdict"]["safe"] is False
    assert snapshot["reboot_verdict"]["verdict"] == "NOT_SAFE_TO_REBOOT"
    assert any("unpushed commits" in r for r in snapshot["reboot_verdict"]["reasons"])


def test_courier_status_owned_pids_detection(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "worker.pid").write_text("12345\n", encoding="utf-8")
    (run_dir / "launcher.pid").write_text("67890\n", encoding="utf-8")

    monkeypatch.setattr("scripts.courier_status.is_pid_alive", lambda pid: pid == 12345)

    pids = get_owned_pids(tmp_path)
    assert "worker" in pids
    assert pids["worker"]["pid"] == 12345
    assert pids["worker"]["alive"] is True
    assert "launcher" in pids
    assert pids["launcher"]["pid"] == 67890
    assert pids["launcher"]["alive"] is False


def test_courier_status_format_report(tmp_path):
    snapshot = get_critical_snapshot_l0(tmp_path)
    report = format_status_report(snapshot)
    assert "CRITICAL SNAPSHOT L0" in report
    assert "Reboot Verdict" in report
    assert "SAFE_TO_REBOOT" in report


def test_courier_status_cli_execution(tmp_path):
    env = os.environ.copy()
    env["COURIER_HOME"] = str(tmp_path)

    script = Path(__file__).resolve().parent.parent / "scripts" / "courier_status.py"

    # Test --json
    proc_json = subprocess.run([sys.executable, str(script), "--json"], capture_output=True, text=True, check=False, env=env)
    assert proc_json.returncode == 0
    data = json.loads(proc_json.stdout)
    assert data["schema_version"] == "1.0"

    # Test --write-snapshot
    proc_write = subprocess.run([sys.executable, str(script), "--write-snapshot"], capture_output=True, text=True, check=False, env=env)
    assert proc_write.returncode == 0
    snapshot_file = tmp_path / "run" / "critical_snapshot_l0.json"
    assert snapshot_file.is_file()
    saved = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "1.0"

    # Test --reboot-check
    proc_check = subprocess.run([sys.executable, str(script), "--reboot-check"], capture_output=True, text=True, check=False, env=env)
    assert proc_check.returncode in (0, 1)
