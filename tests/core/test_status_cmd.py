"""Read-only courier-core status subcommand."""

import json
import subprocess
import sys
from pathlib import Path

from core_builders import Attempt, created, golden_path
from courier_core.journal import Journal
from courier_core.state_machine import TaskStatus
from courier_core.status_cmd import main as status_main


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_status_reports_complete_task(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    with Journal(home / "courier.db") as journal:
        for event in golden_path():
            journal.append(event)
    code = status_main(["--home", str(home)])
    assert code == 0


def test_status_json_blocked_task(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    with Journal(home / "courier.db") as journal:
        journal.append(created(task_id="blocked-1", effect_class="non_idempotent"))
        attempt = Attempt(task_id="blocked-1")
        for event in attempt.claimed(), attempt.started(), attempt.lease_expired():
            journal.append(event)
    out = subprocess.check_output(
        [sys.executable, "-m", "courier_core.cli", "status", "--home", str(home), "--json"],
        cwd=str(REPO_ROOT), text=True,
    )
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["task_counts"].get(TaskStatus.RETRY_PENDING.value, 0) >= 1
    assert any(row["task_id"] == "blocked-1" for row in payload["needs_attention"])


def test_status_missing_journal(tmp_path):
    home = tmp_path / "empty"
    home.mkdir()
    assert status_main(["--home", str(home)]) == 1
