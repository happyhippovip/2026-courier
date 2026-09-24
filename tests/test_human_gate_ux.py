import json
import sys
from pathlib import Path
import pytest

from scripts.human_gate_ux import run_human_gate, main


def test_human_gate_approve_creates_atomic_receipt(tmp_path: Path):
    payload_file = tmp_path / "gate_payload.json"
    payload_data = {
        "action": "DEPLOY_TO_PRODUCTION",
        "artifacts": ["dist.zip"],
        "reason": "Release readiness verified",
    }
    payload_file.write_text(json.dumps(payload_data), encoding="utf-8")

    record = run_human_gate(str(payload_file), decision="APPROVE", quiet=True)
    assert record is not None
    assert record["status"] == "APPROVED"
    assert record["action"] == "DEPLOY_TO_PRODUCTION"
    assert "identity" in record
    assert "timestamp" in record

    # Verify receipt on disk
    approval_file = tmp_path / "gate_payload.json.approval"
    assert approval_file.is_file()
    saved = json.loads(approval_file.read_text(encoding="utf-8"))
    assert saved["status"] == "APPROVED"


def test_human_gate_reject_leaves_no_receipt(tmp_path: Path):
    payload_file = tmp_path / "gate_payload.json"
    payload_data = {
        "action": "DROP_DATABASE",
        "artifacts": [],
        "reason": "Test dangerous action",
    }
    payload_file.write_text(json.dumps(payload_data), encoding="utf-8")

    record = run_human_gate(str(payload_file), decision="REJECT", quiet=True)
    assert record is None

    approval_file = tmp_path / "gate_payload.json.approval"
    assert not approval_file.exists()


def test_human_gate_non_interactive_auto_rejects(tmp_path: Path, monkeypatch):
    payload_file = tmp_path / "gate_payload.json"
    payload_file.write_text(json.dumps({"action": "ACTION", "reason": "TEST"}), encoding="utf-8")

    def mock_input(prompt):
        raise EOFError()

    monkeypatch.setattr("builtins.input", mock_input)
    record = run_human_gate(str(payload_file), decision=None, auto_reject_non_interactive=True, quiet=True)
    assert record is None


def test_human_gate_cli(tmp_path: Path, capsys, monkeypatch):
    payload_file = tmp_path / "gate_payload.json"
    payload_file.write_text(json.dumps({"action": "CLI_ACTION", "reason": "CLI_TEST"}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["human_gate_ux.py", str(payload_file), "--decision", "APPROVE", "--json"],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "APPROVED"
    assert res["action"] == "CLI_ACTION"
