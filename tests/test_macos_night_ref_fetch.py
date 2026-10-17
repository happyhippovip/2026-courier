"""Ref freshness for the macOS Muse night runner.

Regression: batches 82/83 verified "current" origin/integration/v1 against a
30h-stale remote-tracking ref (dirty checkout skips pull --ff-only; nothing
ever fetched), then idled while trunk had moved. The runner must refresh the
integration/v1 ref before the worker verifies truth, without aborting offline.
"""
from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "macos_muse_night_once.sh"


def _lines():
    return SCRIPT.read_text(encoding="utf-8").splitlines()


def test_fetch_integration_ref_before_worker_exec():
    lines = _lines()
    fetch_idx = [i for i, l in enumerate(lines)
                 if re.search(r"git\s+fetch\b.*integration/v1", l)]
    assert fetch_idx, "runner must refresh the integration/v1 ref"
    exec_idx = [i for i, l in enumerate(lines) if "muse exec" in l]
    assert exec_idx, "muse exec invocation missing"
    assert min(fetch_idx) < min(exec_idx), "ref refresh must precede the worker"


def test_fetch_failure_does_not_abort_run():
    for l in _lines():
        s = l.strip()
        if re.search(r"git\s+fetch\b.*integration/v1", s):
            assert "|| exit" not in s and not s.startswith("set -e"), (
                "offline fetch failure must degrade to a logged skip, not abort"
            )
