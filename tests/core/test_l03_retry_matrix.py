import pytest
from courier_core.state_machine import TaskState, Decision, TaskStatus, decide_after_failure

# L03: RETRY_RED_TEST_MATRIX
# This matrix maps the Uncertainty Contract from L02 to exact deterministic expected decisions.

@pytest.mark.parametrize("effect_class, started, failure_kind, retryable_claim, expected_decision", [
    # 1. Unstarted Tasks (Always safe to retry)
    ("idempotent", False, "lease_lost", None, Decision.RETRY),
    ("non_idempotent", False, "lease_lost", None, Decision.RETRY),
    ("idempotent", False, "rejected", True, Decision.RETRY),
    ("non_idempotent", False, "rejected", True, Decision.RETRY),
    
    # 2. Started Idempotent Tasks (Safe to retry, unless explicitly refused by worker)
    ("idempotent", True, "lease_lost", None, Decision.RETRY),
    ("idempotent", True, "rejected", True, Decision.RETRY),
    ("idempotent", True, "rejected", None, Decision.RETRY),
    # If the worker explicitly says retryable=False, we should respect it
    ("idempotent", True, "rejected", False, Decision.FAIL),
    
    # 3. Started Non-Idempotent Tasks (Uncertainty State -> MUST BLOCK)
    ("non_idempotent", True, "lease_lost", None, Decision.BLOCK),
    # The L01 Gap: worker says retryable=True, but we MUST BLOCK
    ("non_idempotent", True, "rejected", True, Decision.BLOCK),
    ("non_idempotent", True, "rejected", False, Decision.BLOCK),
    ("non_idempotent", True, "rejected", None, Decision.BLOCK),
])
def test_retry_uncertainty_matrix(effect_class, started, failure_kind, retryable_claim, expected_decision):
    state = TaskState(
        task_id="T1",
        status=TaskStatus.RETRY_PENDING,
        adapter="synthetic",
        params={},
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=60,
        effect_class=effect_class,
        started=started,
        failure_kind=failure_kind,
        retryable=retryable_claim
    )
    
    # Evaluate the current implementation against the truthful L02 contract
    actual_decision = decide_after_failure(state)
    
    assert actual_decision == expected_decision, (
        f"FAILED CONTRACT: effect_class={effect_class}, started={started}, "
        f"failure={failure_kind}, claim={retryable_claim}. "
        f"Expected {expected_decision}, got {actual_decision}."
    )

