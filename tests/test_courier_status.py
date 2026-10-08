"""Regression: courier_status reads the real tree state from any CWD."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from courier_status import main


@pytest.fixture
def stateroot(tmp_path):
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"status": "DONE"},
                    {"status": "UNASSIGNED"},
                    {"status": "UNASSIGNED"},
                ],
            },
            "g2": {"status": "DONE", "workflow_plan": [{"status": "UNASSIGNED"}]},
        }
    }
    (state_dir / "central_state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def test_reports_yellow_counts(stateroot, capsys):
    assert main(root=stateroot) == 0
    out = capsys.readouterr().out
    assert "Health: YELLOW" in out
    assert "Unassigned P0 Tasks: 2" in out  # g2 is DONE, its step does not count
    assert "Active Goals: 1" in out


def test_green_when_nothing_unassigned(tmp_path, capsys):
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "central_state.json").write_text(
        json.dumps({"goals": {"g": {"status": "ACTIVE", "workflow_plan": []}}}),
        encoding="utf-8",
    )
    assert main(root=tmp_path) == 0
    assert "Health: GREEN" in capsys.readouterr().out


def test_missing_state_reports_no_ledger(tmp_path, capsys):
    assert main(root=tmp_path) == 0
    assert "No ledger found" in capsys.readouterr().out


def test_corrupt_state_fails_loud_without_traceback(tmp_path, capsys):
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "central_state.json").write_text("{not json", encoding="utf-8")
    assert main(root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "unreadable" in out


def test_ignores_caller_cwd(stateroot, tmp_path, monkeypatch, capsys):
    # Regression: the state path was CWD-relative, so running from another
    # directory reported "No ledger found" for a tree that has one.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert main(root=stateroot) == 0
    assert "Health: YELLOW" in capsys.readouterr().out
