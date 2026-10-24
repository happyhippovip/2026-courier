"""O7-08 (B4 A->B->C bytes): bytes that changed after hop B was posted must not PASS.

Guard (holds, tests/test_ledger_chain_abcd_restart.py:128 and
test_ledger_bridge_verified_inputs.py:173): tampered upstream bytes *before* B is
posted block B with input_digest_mismatch.
Defect (strict xfail): the digest is checked once, at post time
(scripts/ledger_v1_bridge.py:282-290 -> _resolve_inputs :498-499). No adapter
reads params.inputs (only adapters/provider_exec.py mentions "inputs", in a
docstring), and _feedback (ledger_v1_bridge.py:121-240) does not re-check
them before FINAL. If A's bytes change after B was posted, B still runs and
its FINAL evidence names the old sha256 while different bytes sit on disk.
Synthetic adapter only; real controller + worker, local, 0 EUR.
"""
import hashlib

import pytest

from tests.test_ledger_bridge_verified_inputs import (
    _bridge, _created, _finals, _run_a, _setup, _wait_complete,
)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-08/B4: inputs are verified at post time only; B finalizes over changed bytes")
def test_bytes_changed_after_b_was_posted_do_not_finalize_b(tmp_path):
    courier, home = _setup(tmp_path, ["A"], ["A"])
    try:
        task_a, _ = _run_a(courier, home)
        artifact = courier.api.get(f"/v1/tasks/{task_a}/result", timeout=5).json()["artifacts"][0]
        posted = _bridge(home, courier.base_url)          # FINAL A, then post B with verified inputs
        assert posted.returncode == 0, posted.stderr + posted.stdout
        task_b = next(e["task_id"] for e in _created(courier) if e["task_id"] != task_a)
        b_inputs = courier.api.get(f"/v1/tasks/{task_b}", timeout=5).json()["params"]["inputs"]
        assert b_inputs[0]["sha256"] == artifact["sha256"]

        (home / artifact["path"]).write_bytes(b"tampered after B was posted")
        on_disk = hashlib.sha256((home / artifact["path"]).read_bytes()).hexdigest()
        assert on_disk != artifact["sha256"]

        worker = courier.start_worker()
        _wait_complete(courier, task_b)
        courier.stop_worker_graceful(worker, timeout=15)
        _bridge(home, courier.base_url)
        finals_b = [e for e in _finals(home) if e.mission_id == "B"]
        # Expected after a fix: B is not FINAL over bytes that no longer match its inputs.
        assert finals_b == [], [e.evidence_ref for e in finals_b]
    finally:
        courier.close()
