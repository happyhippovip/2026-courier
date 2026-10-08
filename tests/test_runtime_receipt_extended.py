import json
import pytest

from courier_runtime.receipt import (
    ACTIONS,
    OUTCOMES,
    ReceiptError,
    RecoveryReceipt,
    validate,
)

NOW = 10_000.0


def make_receipt(**kw):
    base = dict(
        workkey="wk-prod-1",
        session_id="sess-xyz",
        incident_fingerprint="fp-8891",
        detected_state="SURFACE_CORRUPTED",
        detected_at=NOW,
        what_failed="surface",
        positive_evidence=None,
        survived={"process_alive": True, "lease_valid": True, "last_checkpoint_id": "c7"},
        action="RECONNECT_SURFACE",
        outcome="RECOVERED",
        after_snapshot="cs0-2",
        progress_after_detection=True,
    )
    base.update(kw)
    return RecoveryReceipt(**base)


class TestRecoveryReceiptExtended:
    """Rigorous edge-case coverage for RecoveryReceipt verification rules."""

    def test_invalid_actions_rejected(self):
        for bad_action in ["KILL_ALL", "ABORT", "FORCE_RESTART", ""]:
            with pytest.raises(ReceiptError, match="unknown action"):
                validate(make_receipt(action=bad_action), set())

    def test_valid_actions_accepted(self):
        for act in ACTIONS:
            if act == "RESUME_FROM_CHECKPOINT":
                r = make_receipt(action=act, resume_from={"ckpt": "c1"})
            elif act == "RETRY_AUTHORIZED_REQUIRED":
                r = make_receipt(action=act, outcome="WAITING", after_snapshot=None, progress_after_detection=False)
            elif act == "NEEDS_YOU":
                r = make_receipt(action=act, outcome="WAITING", after_snapshot=None, progress_after_detection=False)
            else:
                r = make_receipt(action=act)
            assert validate(r, set()).action == act

    def test_invalid_outcomes_rejected(self):
        for bad_outcome in ["DONE", "SUCCESS", "TERMINATED", "PENDING"]:
            with pytest.raises(ReceiptError, match="unknown outcome"):
                validate(make_receipt(outcome=bad_outcome), set())

    def test_valid_outcomes_accepted(self):
        for outcome in OUTCOMES:
            if outcome == "RECOVERED":
                r = make_receipt(outcome=outcome)
            elif outcome == "FAILED":
                r = make_receipt(
                    outcome=outcome,
                    action="NEEDS_YOU",
                    what_failed="surface",
                    after_snapshot=None,
                    progress_after_detection=False,
                )
            elif outcome == "WAITING":
                r = make_receipt(
                    outcome=outcome,
                    action="NEEDS_YOU",
                    after_snapshot=None,
                    progress_after_detection=False,
                )
            assert validate(r, set()).outcome == outcome

    def test_multiple_retired_identities_partial_ownership_fails(self):
        # Two processes in retired list: PID 101 owned, PID 102 NOT owned -> fails!
        retired = [
            {"pid": 101, "create_time": 12.0},
            {"pid": 102, "create_time": 14.0},
        ]
        owned = {(101, 12.0)}
        with pytest.raises(ReceiptError, match="retired pid 102 was not owned"):
            validate(make_receipt(action="RETIRE_OWNED_TREE", retired=retired), owned)

        # Both owned -> succeeds!
        owned.add((102, 14.0))
        assert validate(make_receipt(action="RETIRE_OWNED_TREE", retired=retired), owned)

    def test_non_idempotent_with_confirmed_effect_can_resume(self):
        # Non-idempotent task whose effect is CONFIRMED can resume from checkpoint
        r = make_receipt(
            action="RESUME_FROM_CHECKPOINT",
            effect_class="non_idempotent",
            effect_confirmed=True,
            resume_from={"checkpoint_id": "c7"},
        )
        assert validate(r, set()).action == "RESUME_FROM_CHECKPOINT"

    def test_resume_missing_resume_from_rejected(self):
        # Even if idempotent, RESUME_FROM_CHECKPOINT requires resume_from dict
        r = make_receipt(
            action="RESUME_FROM_CHECKPOINT",
            effect_class="idempotent",
            resume_from=None,
        )
        with pytest.raises(ReceiptError, match="resume needs a resume_from checkpoint"):
            validate(r, set())

    def test_recovered_missing_after_snapshot_rejected(self):
        # Progress happened, but after_snapshot is missing -> invalid
        r = make_receipt(
            outcome="RECOVERED",
            after_snapshot=None,
            progress_after_detection=True,
        )
        with pytest.raises(ReceiptError, match="RECOVERED needs an after-snapshot"):
            validate(r, set())

    def test_failed_task_requires_positive_evidence(self):
        for failed_type in ["task", "worker_process"]:
            # Without evidence -> raises
            r_no_ev = make_receipt(
                what_failed=failed_type,
                outcome="FAILED",
                action="NEEDS_YOU",
                positive_evidence=None,
                after_snapshot=None,
                progress_after_detection=False,
            )
            with pytest.raises(ReceiptError, match="FAILED needs positive failure evidence"):
                validate(r_no_ev, set())

            # With evidence -> passes
            r_with_ev = make_receipt(
                what_failed=failed_type,
                outcome="FAILED",
                action="NEEDS_YOU",
                positive_evidence="exit_code=137 OOMKilled",
                after_snapshot=None,
                progress_after_detection=False,
            )
            assert validate(r_with_ev, set()).outcome == "FAILED"

    def test_serialization_fields_roundtrip_fidelity(self):
        r = make_receipt(
            effect_class="idempotent",
            evidence_refs=["hash:abc", "hash:def"],
            before_snapshot="snap-before-01",
            after_snapshot="snap-after-02",
        )
        raw_json = r.to_json()
        data = json.loads(raw_json)
        assert data["receipt_id"].startswith("rr-")
        assert data["evidence_refs"] == ["hash:abc", "hash:def"]
        assert data["before_snapshot"] == "snap-before-01"

        reconstructed = RecoveryReceipt.from_json(raw_json)
        assert reconstructed == r
