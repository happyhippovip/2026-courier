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


def test_pilot_gate_does_not_count_a_symlink(tmp_path, monkeypatch):
    def report(root):
        monkeypatch.setattr(pgrc, "__file__", str(root / "scripts" / "pilot_gate_readiness_check.py"))
        with patch("builtins.print") as mock_print:
            code = pgrc.check_pilot_gate_readiness()
        printed = json.loads(mock_print.call_args[0][0])
        return code, printed["status"], printed["prerequisites"]["PILOT_DUMMY_TASK"]

    file_root = tmp_path / "file-case"
    ops = file_root / "ops" / "ai"
    ops.mkdir(parents=True)
    outside = tmp_path / "outside-task.json"
    outside.write_text("SECRET-PILOT\n", encoding="utf-8")
    (ops / "PRE_CODEX_HANDOFF.md").write_text("local\n", encoding="utf-8")
    (ops / "PROOF_CARD.md").write_text("local\n", encoding="utf-8")
    (ops / "PILOT_DUMMY_TASK.json").symlink_to(outside)
    file_seen = report(file_root)

    parent_root = tmp_path / "parent-case"
    outside_dir = tmp_path / "outside-ai"
    outside_dir.mkdir()
    for name in ("PRE_CODEX_HANDOFF.md", "PROOF_CARD.md", "PILOT_DUMMY_TASK.json"):
        (outside_dir / name).write_text("SECRET-PILOT\n", encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_root / "ops").mkdir(parents=True)
    (parent_root / "ops" / "ai").symlink_to(outside_dir)
    parent_seen = report(parent_root)
    names = sorted(path.name for path in outside_dir.iterdir())
    assert (file_seen, parent_seen, "SECRET-PILOT" in outside.read_text(encoding="utf-8"), names) == (
        (1, "BLOCKED", False),
        (1, "BLOCKED", False),
        True,
        ["PILOT_DUMMY_TASK.json", "PRE_CODEX_HANDOFF.md", "PROOF_CARD.md", "keep.txt"],
    )


@patch("sys.exit")
def test_main(mock_exit, monkeypatch):
    import runpy
    # Prevent the actual script from failing if files don't exist by overriding repo root
    # or just let it run. Let's just let it run and check that sys.exit was called.
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "pilot_gate_readiness_check.py"), run_name="__main__")
    mock_exit.assert_called_once()
