import pytest

from courier_runtime.receipt import ReceiptError, RecoveryReceipt, validate

NOW = 10_000.0


def receipt(**kw):
    base = dict(workkey="wk", session_id="s1", incident_fingerprint="fp", detected_state="SURFACE_CORRUPTED",
                detected_at=NOW, what_failed="surface", positive_evidence=None,
                survived={"process_alive": True, "lease_valid": True, "last_checkpoint_id": "c7"},
                action="RECONNECT_SURFACE", outcome="RECOVERED", after_snapshot="cs0-2",
                progress_after_detection=True)
    base.update(kw)
    return RecoveryReceipt(**base)


def test_surface_recovery_receipt_round_trips():
    r = validate(receipt(), set())
    assert validate(RecoveryReceipt.from_json(r.to_json()), set()) == r


def test_only_owned_processes_may_be_retired():
    retired = [{"pid": 42, "create_time": 5.0}]
    with pytest.raises(ReceiptError):
        validate(receipt(action="RETIRE_OWNED_TREE", retired=retired), {(42, 6.0)})
    assert validate(receipt(action="RETIRE_OWNED_TREE", retired=retired), {(42, 5.0)})


def test_non_idempotent_unconfirmed_effect_is_never_resumed():
    with pytest.raises(ReceiptError):
        validate(receipt(action="RESUME_FROM_CHECKPOINT", effect_class="non_idempotent",
                         resume_from={"checkpoint_id": "c7"}), set())
    validate(receipt(action="RETRY_AUTHORIZED_REQUIRED", effect_class="non_idempotent", outcome="WAITING",
                     after_snapshot=None, progress_after_detection=False), set())


def test_recovered_needs_progress_after_detection():
    with pytest.raises(ReceiptError):
        validate(receipt(progress_after_detection=False), set())


def test_failed_needs_positive_evidence():
    with pytest.raises(ReceiptError):
        validate(receipt(what_failed="worker_process", outcome="FAILED", action="NEEDS_YOU"), set())
    validate(receipt(what_failed="worker_process", outcome="FAILED", action="NEEDS_YOU",
                     positive_evidence="exit_code=1"), set())


def test_unknown_outcome_and_action_rejected():
    with pytest.raises(ReceiptError, match="unknown outcome DONE"):
        validate(receipt(outcome="DONE"), set())
    with pytest.raises(ReceiptError, match="unknown outcome TASK_COMPLETE"):
        validate(receipt(outcome="TASK_COMPLETE"), set())
    with pytest.raises(ReceiptError, match="unknown action UNKNOWN"):
        validate(receipt(action="UNKNOWN"), set())
    with pytest.raises(ReceiptError, match="unknown action TASK_COMPLETE"):
        validate(receipt(action="TASK_COMPLETE"), set())


def test_resume_from_checkpoint_requires_resume_from():
    with pytest.raises(ReceiptError, match="resume needs a resume_from checkpoint"):
        validate(receipt(action="RESUME_FROM_CHECKPOINT", resume_from=None), set())


def test_recovered_needs_after_snapshot():
    with pytest.raises(ReceiptError, match="RECOVERED needs an after-snapshot"):
        validate(receipt(after_snapshot=None), set())


def test_failed_task_needs_positive_evidence():
    with pytest.raises(ReceiptError, match="FAILED needs positive failure evidence"):
        validate(receipt(what_failed="task", outcome="FAILED", action="NEEDS_YOU", positive_evidence=None), set())

