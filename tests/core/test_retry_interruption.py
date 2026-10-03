from courier_core.retry_engine import RetryEngine, RetryPolicy
from courier_core.adapter_errors import MissingElementError, SurfaceCorruptedError, ProviderAuthError
from courier_core.interruption_budget import InterruptionBudget
import time

def test_retry_engine_transient():
    engine = RetryEngine(RetryPolicy(max_retries=3, base_backoff_sec=1.0))
    err = MissingElementError("btn")
    
    res1 = engine.calculate_action(err, attempt=0)
    assert res1["action"] == "RETRY"
    assert res1["delay_sec"] == 1.0
    
    res2 = engine.calculate_action(err, attempt=1)
    assert res2["action"] == "RETRY"
    assert res2["delay_sec"] == 2.0
    
    res_fail = engine.calculate_action(err, attempt=3)
    assert res_fail["action"] == "FAIL"
    assert res_fail["reason"] == "MAX_RETRIES_EXCEEDED"

def test_retry_engine_fatal_and_user():
    engine = RetryEngine(RetryPolicy(max_retries=3, base_backoff_sec=1.0))
    
    res_fatal = engine.calculate_action(SurfaceCorruptedError(), attempt=0)
    assert res_fatal["action"] == "FAIL"
    
    res_user = engine.calculate_action(ProviderAuthError(), attempt=0)
    assert res_user["action"] == "ESCALATE"

def test_interruption_budget():
    budget = InterruptionBudget(max_interruptions=2, window_sec=10.0)
    
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False # Budget exhausted
