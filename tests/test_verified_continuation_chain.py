"""A -> B -> C verified continuation chain (scripts/verified_continuation.py).

Positive path: three units across Mode A/B/C hand off automatically with
checkpoints that link each unit to its successor.
Negative path: a failing middle unit stops the chain; C is never claimed.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verified_continuation import ExecutionMode, VerifiedContinuation

REPO = Path(__file__).resolve().parents[1]


def _chain():
    return [
        {"task_id": "t-a", "workkey": "CHAIN_A", "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC},
        {
            "task_id": "t-b-chain-test",
            "workkey": "CHAIN_B",
            "mode": ExecutionMode.MODE_B_GOOGLE_BUILDER,
            "instruction": "chain test unit B",
            "allowed_scope": ["happyhippovip/2026-courier"],
        },
        {"task_id": "t-c", "workkey": "CHAIN_C", "mode": ExecutionMode.MODE_C_AUTONOMOUS_SCHEDULE},
    ]


def test_a_b_c_chain_hands_off_without_manual_prompt(tmp_path):
    engine = VerifiedContinuation(ledger_dir=tmp_path)
    report = engine.run_sequential_chain(_chain())

    assert report["status"] == "PASS"
    assert report["units_completed"] == ["CHAIN_A", "CHAIN_B", "CHAIN_C"]
    assert report["manual_prompts_required"] == 0
    assert report["not_started"] == []

    links = {}
    for key in report["units_completed"]:
        cp = json.loads((tmp_path / "checkpoints" / f"{key}.checkpoint.json").read_text(encoding="utf-8"))
        assert cp["status"] == "PASS"
        links[key] = cp["next_workkey"]
    assert links == {"CHAIN_A": "CHAIN_B", "CHAIN_B": "CHAIN_C", "CHAIN_C": None}
    # all claims released
    assert list((tmp_path / "claims").glob("*.claim")) == []


def test_failing_b_stops_chain_and_c_never_claimed(tmp_path):
    units = _chain()
    units[1] = {"task_id": "t-b-fail", "workkey": "CHAIN_B", "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
                "command": [sys.executable, "-c", "import sys; sys.exit(3)"]}
    engine = VerifiedContinuation(ledger_dir=tmp_path)
    report = engine.run_sequential_chain(units)

    assert report["status"] == "FAIL"
    assert report["units_completed"] == ["CHAIN_A"]
    assert report["failed_at"] == "CHAIN_B"
    assert report["not_started"] == ["CHAIN_C"]
    assert not (tmp_path / "checkpoints" / "CHAIN_B.checkpoint.json").exists()
    assert not (tmp_path / "checkpoints" / "CHAIN_C.checkpoint.json").exists()
    assert list((tmp_path / "claims").glob("*.claim")) == []


def test_chain_rejects_duplicate_workkeys(tmp_path):
    engine = VerifiedContinuation(ledger_dir=tmp_path)
    with pytest.raises(ValueError):
        engine.run_sequential_chain([{"workkey": "X"}, {"workkey": "X"}])


def test_cli_runs_standalone_without_pythonpath(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "verified_continuation.py"), "--verify-chain",
         "--ledger-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True, timeout=120,
        env={k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"},
    )
    assert proc.returncode == 0, proc.stderr
    assert '"status": "PASS"' in proc.stdout
