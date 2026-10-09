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


@pytest.mark.parametrize("effect_class", [None, "", "future_financial_effect", "IDEMPOTENT"])
@pytest.mark.parametrize("confirmed", [False, True])
def test_unknown_effect_class_never_authorizes_automatic_resume(effect_class, confirmed):
    r = receipt(action="RESUME_FROM_CHECKPOINT", effect_class=effect_class,
                effect_confirmed=confirmed, resume_from={"checkpoint_id": "c7"})
    with pytest.raises(ReceiptError):
        validate(RecoveryReceipt.from_json(r.to_json()), set())


@pytest.mark.parametrize("confirmation", ["false", "true", 1, {}, [True]])
def test_non_idempotent_resume_requires_literal_confirmation(confirmation):
    with pytest.raises(ReceiptError):
        validate(receipt(action="RESUME_FROM_CHECKPOINT", effect_class="non_idempotent",
                         effect_confirmed=confirmation, resume_from={"checkpoint_id": "c7"}), set())


@pytest.mark.parametrize("effect_class,confirmed", [("idempotent", False), ("non_idempotent", True)])
def test_known_safe_resume_contract_remains_valid(effect_class, confirmed):
    r = receipt(action="RESUME_FROM_CHECKPOINT", effect_class=effect_class,
                effect_confirmed=confirmed, resume_from={"checkpoint_id": "c7"})
    assert validate(r, set()) is r


def test_unknown_effect_can_be_parked_without_fabricating_completion():
    r = receipt(action="RETRY_AUTHORIZED_REQUIRED", outcome="WAITING", effect_class="future_effect",
                after_snapshot=None, progress_after_detection=False)
    assert validate(r, set()).outcome == "WAITING"


@pytest.mark.parametrize("progress", ["false", "true", 1, [True]])
def test_recovered_rejects_truthy_values_in_place_of_progress_evidence(progress):
    with pytest.raises(ReceiptError):
        validate(receipt(progress_after_detection=progress), set())


@pytest.mark.parametrize("snapshot", [True, 1, ["snapshot"], " "])
def test_recovered_requires_a_nonempty_snapshot_reference(snapshot):
    with pytest.raises(ReceiptError):
        validate(receipt(after_snapshot=snapshot), set())
