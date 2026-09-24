#!/usr/bin/env python3
"""Tests for scripts/build_handoff_package.py."""

import json
from pathlib import Path
import pytest
from scripts.build_handoff_package import build_package, main


def test_build_package_input_validation():
    with pytest.raises(ValueError):
        build_package("", "task_1", "instruction_1")
    with pytest.raises(ValueError):
        build_package("wf_1", "", "instruction_1")
    with pytest.raises(ValueError):
        build_package("wf_1", "task_1", "")


def test_build_package_success(tmp_path: Path):
    test_file = tmp_path / "sample.py"
    test_file.write_text("print('hello')", encoding="utf-8")

    package = build_package(
        workflow_id="wf_test_100",
        task_id="task_test_100",
        instruction="Run regression tests",
        files=["sample.py"],
        repo_dir=tmp_path,
    )

    assert package["workflow_id"] == "wf_test_100"
    assert package["task_id"] == "task_test_100"
    assert package["instruction"] == "Run regression tests"
    assert "context_delta" in package
    assert "file_manifest" in package["context_delta"]
    assert "task_dedupe_hash" in package["context_delta"]


def test_main_cli_positional(tmp_path: Path, capsys):
    ret = main(["wf_pos", "task_pos", "instr_pos"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["workflow_id"] == "wf_pos"
    assert data["task_id"] == "task_pos"
