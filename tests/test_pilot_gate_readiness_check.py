import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import scripts.pilot_gate_readiness_check as pgrc

def test_check_pilot_gate_readiness_pass(tmp_path, monkeypatch):
    # Mock repo root to tmp_path
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    
    # Create the required files
    ops_dir = tmp_path / "ops" / "ai"
    ops_dir.mkdir(parents=True, exist_ok=True)
    (ops_dir / "PRE_CODEX_HANDOFF.md").touch()
    (ops_dir / "PROOF_CARD.md").touch()
    (ops_dir / "PILOT_DUMMY_TASK.json").touch()

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 0
    mock_print.assert_called_once()
    printed_json = json.loads(mock_print.call_args[0][0])
    assert printed_json["status"] == "PASS"
    assert printed_json["prerequisites"]["PRE_CODEX_HANDOFF"] is True
    assert printed_json["prerequisites"]["PROOF_CARD"] is True
    assert printed_json["prerequisites"]["PILOT_DUMMY_TASK"] is True


def test_check_pilot_gate_readiness_blocked_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    
    # Missing files
    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 1
    mock_print.assert_called_once()
    printed_json = json.loads(mock_print.call_args[0][0])
    assert printed_json["status"] == "BLOCKED"
    assert printed_json["reason"] == "Missing prerequisites"
    assert printed_json["prerequisites"]["PRE_CODEX_HANDOFF"] is False
    assert printed_json["prerequisites"]["PROOF_CARD"] is False
    assert printed_json["prerequisites"]["PILOT_DUMMY_TASK"] is False


def test_pre_codex_evidence_gaps_are_counted_when_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()
        again = pgrc.check_pilot_gate_readiness()

    assert exit_code == 1 and again == 1
    first = json.loads(mock_print.call_args_list[0][0][0])
    second = json.loads(mock_print.call_args_list[1][0][0])
    assert first["pre_codex_evidence_gap_count"] == 3
    assert first["pre_codex_evidence_gaps"] == [
        "PRE_CODEX_HANDOFF",
        "PROOF_CARD",
        "PILOT_DUMMY_TASK",
    ]
    assert second == first


def test_pre_codex_evidence_gap_count_is_zero_when_files_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    ops_dir = tmp_path / "ops" / "ai"
    ops_dir.mkdir(parents=True)
    (ops_dir / "PRE_CODEX_HANDOFF.md").touch()
    (ops_dir / "PROOF_CARD.md").touch()
    (ops_dir / "PILOT_DUMMY_TASK.json").touch()

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 0
    printed = json.loads(mock_print.call_args[0][0])
    assert printed["pre_codex_evidence_gap_count"] == 0
    assert printed["pre_codex_evidence_gaps"] == []


def test_pre_codex_evidence_gap_names_only_the_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    ops_dir = tmp_path / "ops" / "ai"
    ops_dir.mkdir(parents=True)
    (ops_dir / "PROOF_CARD.md").touch()
    (ops_dir / "PILOT_DUMMY_TASK.json").touch()
    (ops_dir / "notes.txt").touch()

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 1
    printed = json.loads(mock_print.call_args[0][0])
    assert printed["status"] == "BLOCKED"
    assert printed["pre_codex_evidence_gap_count"] == 1
    assert printed["pre_codex_evidence_gaps"] == ["PRE_CODEX_HANDOFF"]


@patch("sys.exit")
def test_main(mock_exit, monkeypatch):
    import runpy
    # Prevent the actual script from failing if files don't exist by overriding repo root
    # or just let it run. Let's just let it run and check that sys.exit was called.
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "pilot_gate_readiness_check.py"), run_name="__main__")
    mock_exit.assert_called_once()
