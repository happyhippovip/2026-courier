from pathlib import Path

import pytest
import os
import sys
from scripts.check_pilot_readiness import check_readiness

def test_check_readiness_success(monkeypatch, capsys):
    def mock_exists(path):
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()
        
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ALL PILOT PREREQUISITES PRESENT" in captured.out

def test_check_readiness_failure(monkeypatch, capsys):
    def mock_exists(path):
        # Simulate missing file for the first one
        if path == "ops/ai/PILOT_DUMMY_TASK.json":
            return False
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()
        
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "FAILED: Missing ops/ai/PILOT_DUMMY_TASK.json" in captured.out


def test_readiness_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    names = [
        "PILOT_DUMMY_TASK.json",
        "PILOT_METRICS_AND_CONTRACT.md",
        "PILOT_METRICS_AND_SIGNAL_SPEC.md",
        "PROVIDER_ISOLATION_SPEC.md",
    ]

    def outcome(root):
        monkeypatch.chdir(root)
        try:
            check_readiness()
            err = None
        except ValueError as exc:
            err = str(exc)
        except SystemExit as exc:
            err = exc.code
        return err, capsys.readouterr().out

    file_root = tmp_path / "file-case"
    ai = file_root / "ops" / "ai"
    ai.mkdir(parents=True)
    outside = tmp_path / "outside-task.json"
    outside.write_text('{"goal_id":"SECRET-PILOT"}\n', encoding="utf-8")
    for name in names[1:]:
        (ai / name).write_text("local\n", encoding="utf-8")
    (ai / names[0]).symlink_to(outside)
    file_err, file_out = outcome(file_root)

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    outside_dir = tmp_path / "outside-ai"
    outside_dir.mkdir()
    for name in names:
        (outside_dir / name).write_text('{"goal_id":"SECRET-PILOT"}\n', encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_root / "ops").mkdir()
    (parent_root / "ops" / "ai").symlink_to(outside_dir)
    parent_err, parent_out = outcome(parent_root)
    listed = sorted(path.name for path in outside_dir.iterdir())
    assert (
        file_err,
        "ALL PILOT PREREQUISITES PRESENT" in file_out,
        parent_err,
        "ALL PILOT PREREQUISITES PRESENT" in parent_out,
        "SECRET-PILOT" in outside.read_text(encoding="utf-8"),
        listed,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        True,
        ["PILOT_DUMMY_TASK.json", "PILOT_METRICS_AND_CONTRACT.md", "PILOT_METRICS_AND_SIGNAL_SPEC.md", "PROVIDER_ISOLATION_SPEC.md", "keep.txt"],
    )
