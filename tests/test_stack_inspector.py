#!/usr/bin/env python3
"""Tests for scripts/stack_inspector.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from scripts.stack_inspector import inspect_stack, main


def test_inspect_stack_structure():
    res = inspect_stack(quiet=True)
    assert res["status"] == "SUCCESS"
    assert res["human_gate_required"] is True
    assert res["unattended_merges_allowed"] is False
    assert res["merge_sequence_policy"] == "HUMAN_GATE_ONLY"
    assert isinstance(res["branches"], list)


def test_inspect_stack_phase_detection():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "* windows_lane/W01\n  phase-a/hardening\n  phase-b/cleanup\n  main\n"

    with patch("subprocess.run", return_value=mock_proc):
        res = inspect_stack(quiet=True)
        assert res["current_branch"] == "windows_lane/W01"
        assert res["phase_a_found"] is True
        assert res["phase_b_found"] is True
        assert res["phase_c_found"] is False


def test_main_cli_json(capsys):
    ret = main(["--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["status"] == "SUCCESS"
    assert data["human_gate_required"] is True
