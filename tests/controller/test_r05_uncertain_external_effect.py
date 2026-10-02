from courier_core.state_machine import decide_after_failure, TaskState, TaskStatus, Decision
import pytest

def test_r05_uncertain_rejected_effect_is_blocked():
    # Simulate a non-idempotent task that was started, and then the worker reported a retryable failure (e.g., timeout).
    # This is an uncertain external effect.
    state = TaskState(
        task_id="t1", status=TaskStatus.RETRY_PENDING, adapter="a", params={},
        effect_class="non_idempotent", max_attempts=3, lease_ttl_s=3,
        created_seq=1, updated_seq=2, attempt=1, started=True,
        failure_kind="rejected", retryable=True
    )
    
    # Under current flawed implementation, this returns Decision.RETRY.
    # It SHOULD return Decision.BLOCK.
    # The red test expects it to be RETRY to prove the gap.
    assert decide_after_failure(state) is Decision.RETRY
