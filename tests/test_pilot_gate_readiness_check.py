import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import scripts.pilot_gate_readiness_check as pgrc

def test_check_pilot_gate_readiness_pass(tmp_path, monkeypatch):
    # Files present are necessary and still not a PRE_CODEX_READY claim.
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))

    ops_dir = tmp_path / "ops" / "ai"
    ops_dir.mkdir(parents=True, exist_ok=True)
    (ops_dir / "PRE_CODEX_HANDOFF.md").touch()
    (ops_dir / "PROOF_CARD.md").touch()
    (ops_dir / "PILOT_DUMMY_TASK.json").touch()

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 1
    mock_print.assert_called_once()
    printed_json = json.loads(mock_print.call_args[0][0])
    assert printed_json["status"] == "BLOCKED"
    assert printed_json["reason"] == "PRE_CODEX_NOT_READY"
    assert printed_json["prerequisites"]["PRE_CODEX_HANDOFF"] is True
    assert printed_json["prerequisites"]["PROOF_CARD"] is True
    assert printed_json["prerequisites"]["PILOT_DUMMY_TASK"] is True
    assert printed_json["prerequisites"]["TARGETED_TESTS_GREEN"] is False
    assert printed_json["pre_codex"]["claim_allowed"] is False


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


def test_file_pass_is_not_a_measured_go(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))
    ops_dir = tmp_path / "ops" / "ai"
    ops_dir.mkdir(parents=True)
    (ops_dir / "PRE_CODEX_HANDOFF.md").touch()
    (ops_dir / "PROOF_CARD.md").touch()
    (ops_dir / "PILOT_DUMMY_TASK.json").touch()

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 0
    printed_json = json.loads(mock_print.call_args[0][0])
    assert printed_json["status"] == "PASS"
    assert printed_json["go_decision"] == "NO_GO"
    assert printed_json["go_reason"] == "metrics are not measured"
    for name, metric in printed_json["metrics"].items():
        assert metric["status"] == "NOT_MEASURED", name
        assert metric["actual"] is None
        assert "target" in metric


def test_missing_files_stay_no_go(tmp_path, monkeypatch):
    monkeypatch.setattr(pgrc, "__file__", str(tmp_path / "scripts" / "pilot_gate_readiness_check.py"))

    with patch("builtins.print") as mock_print:
        exit_code = pgrc.check_pilot_gate_readiness()

    assert exit_code == 1
    printed_json = json.loads(mock_print.call_args[0][0])
    assert printed_json["status"] == "BLOCKED"
    assert printed_json["go_decision"] == "NO_GO"


@patch("sys.exit")
def test_main(mock_exit, monkeypatch):
    import runpy
    # Prevent the actual script from failing if files don't exist by overriding repo root
    # or just let it run. Let's just let it run and check that sys.exit was called.
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "pilot_gate_readiness_check.py"), run_name="__main__")
    mock_exit.assert_called_once()
