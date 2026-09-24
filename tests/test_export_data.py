import json
import sys
from pathlib import Path
import pytest

from scripts.export_data import export_customer_data, main


def test_export_customer_data_missing_state(tmp_path: Path):
    nonexistent = tmp_path / "central_state.json"
    res = export_customer_data(
        export_path=str(tmp_path / "out.json"),
        state_file=str(nonexistent),
        quiet=True,
    )
    assert res is None


def test_export_customer_data_success_and_redaction(tmp_path: Path):
    state_file = tmp_path / "central_state.json"
    state_data = {
        "goals": {
            "G-01": {
                "description": "Public Goal 1",
                "status": "COMPLETED",
                "created_at": "2026-09-24T10:00:00Z",
                "completed_at": "2026-09-24T10:30:00Z",
                "internal_secret": "SUPER_SECRET_TOKEN",
            }
        },
        "tasks": {
            "T-01": {
                "type": "video_render",
                "status": "DONE",
                "created_at": "2026-09-24T10:05:00Z",
                "completed_at": "2026-09-24T10:25:00Z",
                "artifacts": ["video.mp4"],
                "error_summary": "",
                "chain_of_thought": "Sensitive thoughts here",
            }
        },
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    out_file = tmp_path / "export" / "customer_export.json"
    exported = export_customer_data(
        export_path=str(out_file),
        state_file=str(state_file),
        quiet=True,
    )

    assert exported is not None
    assert len(exported["goals"]) == 1
    assert exported["goals"][0]["goal_id"] == "G-01"
    assert "internal_secret" not in exported["goals"][0]

    assert len(exported["tasks"]) == 1
    assert exported["tasks"][0]["task_id"] == "T-01"
    assert "chain_of_thought" not in exported["tasks"][0]

    # Verify physical file on disk
    assert out_file.is_file()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["exported_at"] == exported["exported_at"]


def test_export_customer_data_cli(tmp_path: Path, capsys, monkeypatch):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({"goals": {}, "tasks": {}}), encoding="utf-8")
    out_file = tmp_path / "export_cli.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_data.py",
            str(out_file),
            "--state-file", str(state_file),
            "--dry-run",
            "--json",
        ],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert "exported_at" in res
    assert "goals" in res
    assert "tasks" in res
