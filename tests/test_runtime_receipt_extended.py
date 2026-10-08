import pytest
from courier_runtime.receipt import (
    RecoveryReceipt,
    validate,
    ReceiptError,
    ACTIONS,
    OUTCOMES,
)


def test_receipt_action_and_outcome_sets():
    assert "NONE" in ACTIONS
    assert "RECONNECT_SURFACE" in ACTIONS
    assert "RETIRE_OWNED_TREE" in ACTIONS
    assert "RESUME_FROM_CHECKPOINT" in ACTIONS
    assert "RETRY_AUTHORIZED_REQUIRED" in ACTIONS
    assert "NEEDS_YOU" in ACTIONS

    assert "RECOVERED" in OUTCOMES
    assert "FAILED" in OUTCOMES
    assert "WAITING" in OUTCOMES


def test_validate_unknown_action_and_outcome():
    r = RecoveryReceipt(
        workkey="wk-1",
        session_id="s1",
        incident_fingerprint="fp1",
        detected_state="ERR",
        detected_at=1000.0,
        what_failed="surface",
        positive_evidence=None,
        survived={},
        action="INVALID_ACTION",
        outcome="RECOVERED",
    )
    with pytest.raises(ReceiptError) as exc:
        validate(r, set())
    assert "unknown action INVALID_ACTION" in str(exc.value)

    r_bad_outcome = RecoveryReceipt(
        workkey="wk-1",
        session_id="s1",
        incident_fingerprint="fp1",
        detected_state="ERR",
        detected_at=1000.0,
        what_failed="surface",
        positive_evidence=None,
        survived={},
        action="NONE",
        outcome="UNKNOWN_OUTCOME",
    )
    with pytest.raises(ReceiptError) as exc:
        validate(r_bad_outcome, set())
    assert "unknown outcome UNKNOWN_OUTCOME" in str(exc.value)


def test_resume_from_checkpoint_requires_resume_from():
    r = RecoveryReceipt(
        workkey="wk-1",
        session_id="s1",
        incident_fingerprint="fp1",
        detected_state="ERR",
        detected_at=1000.0,
        what_failed="surface",
        positive_evidence=None,
        survived={},
        action="RESUME_FROM_CHECKPOINT",
        outcome="WAITING",
        resume_from=None,  # missing
    )
    with pytest.raises(ReceiptError) as exc:
        validate(r, set())
    assert "resume needs a resume_from checkpoint" in str(exc.value)


def test_task_failed_needs_positive_evidence():
    r = RecoveryReceipt(
        workkey="wk-1",
        session_id="s1",
        incident_fingerprint="fp1",
        detected_state="ERR",
        detected_at=1000.0,
        what_failed="task",
        positive_evidence=None,  # missing
        survived={},
        action="NEEDS_YOU",
        outcome="FAILED",
    )
    with pytest.raises(ReceiptError) as exc:
        validate(r, set())
    assert "FAILED needs positive failure evidence" in str(exc.value)
