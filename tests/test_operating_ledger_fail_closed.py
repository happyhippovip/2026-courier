#!/usr/bin/env python3
"""Fail-closed guards for scripts/operating_ledger.py.

The operating ledger module is NOT authoritative Courier truth and must never
fabricate a DONE goal, costs, or revenue margin. Regression coverage for the
removal of the hardcoded fake-success stub.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts" / "operating_ledger.py"
SPEC = importlib.util.spec_from_file_location("operating_ledger", MOD_PATH)
assert SPEC and SPEC.loader
operating_ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operating_ledger)


def test_read_ledger_does_not_fabricate_done():
    try:
        ledger = operating_ledger.read_ledger()
    except Exception:
        # Fail-closed (raise) is the desired behavior.
        return
    # If it returns instead of raising, it must not claim success.
    goals = ledger.get("goals", []) if isinstance(ledger, dict) else []
    for goal in goals:
        assert goal.get("status") != "DONE", "operating_ledger must not fabricate DONE"
    assert ledger.get("revenue", {}).get("margin") in (None, 0, 0.0), (
        "operating_ledger must not fabricate a revenue margin"
    )


def test_module_is_marked_non_authoritative():
    source = MOD_PATH.read_text(encoding="utf-8")
    assert "DONE" not in source or "must not" in source.lower() or "fabricate" in source.lower(), (
        "operating_ledger must not contain an uncommented fake DONE claim"
    )
