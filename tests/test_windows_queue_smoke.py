from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.windows_queue_smoke as wqs


def test_windows_queue_smoke_default_temp():
    res = wqs.run_windows_queue_smoke()
    assert res["status"] == "PASS"
    assert res["task_status"] == "DONE"


def test_windows_queue_smoke_explicit_dir(tmp_path: Path):
    state_dir = tmp_path / "custom_state"
    res = wqs.run_windows_queue_smoke(state_dir=state_dir)
    assert res["status"] == "PASS"
    assert (state_dir / "queue.json").exists()


def test_main_cli(tmp_path: Path, capsys):
    state_dir = tmp_path / "cli_state"
    code = wqs.main(["--state-dir", str(state_dir), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "PASS"


def test_main_cli_failure(capsys):
    with patch.object(wqs, "run_windows_queue_smoke", side_effect=RuntimeError("Smoke error")):
        code = wqs.main(["--json"])
        assert code == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "FAIL"
        assert "Smoke error" in data["error"]
