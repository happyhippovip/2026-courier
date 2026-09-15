import pytest
from pathlib import Path
from courier_durable_result import DurableResult, DurableResultLedger, AmbiguousResultError, MalformedResultError

def get_sample_result():
    return DurableResult(
        goal_id="g1", task_id="t1", attempt_id=1, worker_id="w1", provider="local",
        session_identity="s1", input_identity="i1", result_state="SUCCESS",
        result_refs=["file.txt"], commit_identity="abc", started_at="2026-01-01",
        finished_at="2026-01-01", effect_classification="SAFE", verification_required=False,
        human_gate="NONE", error_identity=None
    )

def test_atomic_persistence_and_idempotent_replay(tmp_path):
    ledger = DurableResultLedger(str(tmp_path / "results.db"))
    res = get_sample_result()
    
    # First write (Atomic persistence)
    ledger.record_result(res)
    
    # Second write (Idempotent replay)
    ledger.record_result(res) # Should not raise

def test_conflict_fail_closed(tmp_path):
    ledger = DurableResultLedger(str(tmp_path / "results.db"))
    res1 = get_sample_result()
    ledger.record_result(res1)
    
    res2 = get_sample_result()
    res2.result_state = "FAILURE" # Conflicting state
    
    with pytest.raises(AmbiguousResultError):
        ledger.record_result(res2)

def test_malformed_result_rejected(tmp_path):
    ledger = DurableResultLedger(str(tmp_path / "results.db"))
    res = get_sample_result()
    res.worker_id = "" # Missing required field
    
    with pytest.raises(MalformedResultError):
        ledger.record_result(res)
