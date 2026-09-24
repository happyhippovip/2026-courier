import json
import sys
from pathlib import Path
import pytest

from scripts.account_switch import WindowsPrimaryWorker, trigger_account_switch, main


def test_trigger_account_switch_with_active_task(tmp_path: Path):
    state_file = tmp_path / "central_state.json"
    session_file = tmp_path / "account_session.json"

    state_data = {
        "goals": {
            "G-01": {
                "workflow_plan": [
                    {
                        "task_id": "WF-TASK-1",
                        "status": "RUNNING",
                    }
                ]
            }
        }
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    worker = WindowsPrimaryWorker()
    worker.claim_task({"task_id": "WF-TASK-1"})
    # Mock fake owned pid
    worker.owned_pids.add(999999)

    res = trigger_account_switch(
        worker,
        new_account="ENTERPRISE_CORP_01",
        state_file=str(state_file),
        session_file=str(session_file),
        quiet=True,
    )

    assert res["status"] == "SUCCESS"
    assert res["active_account"] == "ENTERPRISE_CORP_01"
    assert len(worker.owned_pids) == 0

    # Verify session file was written atomically
    assert session_file.is_file()
    session = json.loads(session_file.read_text(encoding="utf-8"))
    assert session["active_account"] == "ENTERPRISE_CORP_01"

    # Verify task state resumed to RUNNING
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["goals"]["G-01"]["workflow_plan"][0]["status"] == "RUNNING"


def test_trigger_account_switch_no_active_task(tmp_path: Path):
    session_file = tmp_path / "account_session.json"
    worker = WindowsPrimaryWorker()

    res = trigger_account_switch(
        worker,
        new_account="ANOTHER_ACCOUNT",
        session_file=str(session_file),
        quiet=True,
    )

    assert res["status"] == "SUCCESS"
    assert res["active_account"] == "ANOTHER_ACCOUNT"
    assert session_file.is_file()


def test_account_switch_cli(tmp_path: Path, capsys, monkeypatch):
    session_file = tmp_path / "account_session.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "account_switch.py",
            "--account", "CLI_ACCOUNT_TEST",
            "--session-file", str(session_file),
            "--json",
        ],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "SUCCESS"
    assert res["active_account"] == "CLI_ACCOUNT_TEST"
    assert session_file.is_file()
