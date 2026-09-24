from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.operating_ledger as ol


def test_read_ledger_default(tmp_path: Path):
    ledger = ol.read_ledger(repo_dir=tmp_path)
    assert len(ledger["goals"]) == 1
    assert ledger["goals"][0]["goal_id"] == "g1"
    assert ledger["costs"]["compute"] == 1.50
    assert ledger["revenue"]["margin"] == 8.50


def test_read_ledger_from_state_file(tmp_path: Path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(
        json.dumps({
            "goals": [
                {"goal_id": "g100", "status": "DONE"},
                {"goal_id": "g101", "status": "DONE"},
            ]
        }),
        encoding="utf-8",
    )

    ledger = ol.read_ledger(repo_dir=tmp_path)
    assert len(ledger["goals"]) == 2
    assert ledger["goals"][0]["goal_id"] == "g100"


def test_print_operator_report(tmp_path: Path, capsys):
    ol.print_operator_report(repo_dir=tmp_path, as_json=False)
    captured = capsys.readouterr()
    assert "--- OPERATOR REPORT ---" in captured.out
    assert "Goals Completed: 1" in captured.out
    assert "Revenue Margin: $8.50" in captured.out


def test_main_cli(tmp_path: Path, capsys):
    code = ol.main(["--repo-dir", str(tmp_path), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "goals" in data
    assert "revenue" in data
