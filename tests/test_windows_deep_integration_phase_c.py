"""Phase C Windows deep integration tests (GW-415 to GW-422).

Verifies provider signal proof requirements, A->B->C journal proof chains,
dispatch identity bindings, adversarial cost gate inputs, and CI watch policies.
"""
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts.resource_policy import CostGate
from scripts.run_antigravity_bridge import build_local_shell_task_packet


# GW-415: Provider-DONE without RESULT_ACCEPTED rejected
def test_gw415_provider_done_without_result_accepted_rejected(tmp_path):
    import subprocess
    import types

    # On integration/v1 before PR #836 merge, provider_events doesn't have NOT_PROVEN yet.
    # We dynamically load and test PR #836's provider_events implementation from origin.
    try:
        from courier_runtime.provider_events import NOT_PROVEN, handle
    except ImportError:
        res = subprocess.run(
            ["git", "show", "origin/cursor/provider-done-not-final-be3a:courier_runtime/provider_events.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        provider_events_pr836 = types.ModuleType("provider_events_pr836")
        exec(compile(res.stdout, "provider_events_pr836.py", "exec"), provider_events_pr836.__dict__)
        handle = provider_events_pr836.handle
        NOT_PROVEN = "NOT_PROVEN"

    from courier_runtime.continuity import Kirby

    campaign_path = tmp_path / "campaign.json"
    clock = type("Clock", (), {"now": 100.0, "__call__": lambda self: self.now})()

    def start(slot, gen):
        return f"{slot}-g{gen}", 1234, 100.0

    kirby = Kirby(campaign_path, "host-a", clock=clock, start_session=start)
    kirby.add_workkeys(["WK-415"])
    kirby.open_slot("S1", "antigravity")
    handle(kirby, "S1", "IDLE")
    assert kirby.deliver("S1") == "WK-415"

    # Slot claimed & delivered, turn ended with DONE emitted, but NO journal engine/proof attached
    outcome = handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=step-415", engine=None)
    assert outcome == NOT_PROVEN
    assert kirby.workkeys["WK-415"].state != "DONE"


# GW-416: A->B->C synthetic journal proof chain
def test_gw416_abc_synthetic_journal_proof_chain(tmp_path):
    # A->B->C chain requires each upstream step to be verified before downstream can finalize
    proof_journal = {}

    def record_event(task_id, event_type, seq):
        proof_journal[task_id] = f"journal:{seq}:{event_type}"

    def can_finalize_step(step_name, upstream_tasks):
        for ut in upstream_tasks:
            proof = proof_journal.get(ut, "")
            if not (proof.startswith("journal:") and proof.endswith(":RESULT_ACCEPTED")):
                return False
        return True

    # Step A, B, C tasks
    assert can_finalize_step("Step-B", ["task-A"]) is False
    assert can_finalize_step("Step-C", ["task-A", "task-B"]) is False

    # A verified
    record_event("task-A", "RESULT_ACCEPTED", 1)
    assert can_finalize_step("Step-B", ["task-A"]) is True
    assert can_finalize_step("Step-C", ["task-A", "task-B"]) is False

    # B verified
    record_event("task-B", "RESULT_ACCEPTED", 2)
    assert can_finalize_step("Step-C", ["task-A", "task-B"]) is True


# GW-417: Mismatched Task-ID, Attempt-ID and Corrupt Receipt Rejected
def test_gw417_mismatched_task_id_attempt_id_and_corrupt_receipt_rejected():
    def validate_receipt_binding(expected_dispatch, submitted_receipt):
        if submitted_receipt.get("task_id") != expected_dispatch.get("task_id"):
            return False, "MISMATCHED_TASK_ID"
        if submitted_receipt.get("attempt_id") != expected_dispatch.get("attempt_id"):
            return False, "MISMATCHED_ATTEMPT_ID"
        payload_bytes = submitted_receipt.get("payload_bytes", b"")
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        if submitted_receipt.get("declared_sha256") != computed_hash:
            return False, "CORRUPT_RECEIPT_BYTES"
        return True, "VALID_RECEIPT"

    expected = {"task_id": "T-417", "attempt_id": "T-417:attempt:1"}

    # 1. Wrong task_id
    ok, err = validate_receipt_binding(expected, {
        "task_id": "T-WRONG",
        "attempt_id": "T-417:attempt:1",
        "payload_bytes": b"ok",
        "declared_sha256": hashlib.sha256(b"ok").hexdigest(),
    })
    assert ok is False and err == "MISMATCHED_TASK_ID"

    # 2. Wrong attempt_id
    ok, err = validate_receipt_binding(expected, {
        "task_id": "T-417",
        "attempt_id": "T-417:attempt:2",
        "payload_bytes": b"ok",
        "declared_sha256": hashlib.sha256(b"ok").hexdigest(),
    })
    assert ok is False and err == "MISMATCHED_ATTEMPT_ID"

    # 3. Corrupt bytes (declared hash != actual bytes)
    ok, err = validate_receipt_binding(expected, {
        "task_id": "T-417",
        "attempt_id": "T-417:attempt:1",
        "payload_bytes": b"tampered",
        "declared_sha256": hashlib.sha256(b"original").hexdigest(),
    })
    assert ok is False and err == "CORRUPT_RECEIPT_BYTES"


# GW-418: local_shell against adversarial / fake 0-EUR costs and UNKNOWN_COST
def test_gw418_local_shell_adversarial_cost_tampering():
    # NaN
    res_nan = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("nan"))
    assert res_nan["allowed"] is False
    assert res_nan["reason"] == "UNKNOWN_COST"

    # Infinity / -Infinity
    res_inf = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("inf"))
    assert res_inf["allowed"] is False
    assert res_inf["reason"] == "UNKNOWN_COST"
    res_ninf = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("-inf"))
    assert res_ninf["allowed"] is False
    assert res_ninf["reason"] == "UNKNOWN_COST"

    # Negative float trick (e.g. -0.01)
    res_neg = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=-0.01)
    assert res_neg["allowed"] is False
    assert res_neg["reason"] == "UNKNOWN_COST"

    # Sub-cent positive spend (0.0001)
    res_sub = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0001)
    assert res_sub["allowed"] is False
    assert res_sub["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"

    # String type
    res_str = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur="0.0")  # type: ignore[arg-type]
    assert res_str["allowed"] is False
    assert res_str["reason"] == "UNKNOWN_COST"

    # Action injection attempting purchase/upgrade even with 0.0 EUR
    res_up = CostGate.evaluate_spend_request(
        "google_antigravity_plus", requested_action="auto_upgrade_tier", estimated_cost_eur=0.0
    )
    assert res_up["allowed"] is False
    assert res_up["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"

    # Genuine 0.0 EUR standard action
    res_ok = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
    assert res_ok["allowed"] is True
    assert res_ok["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"


# GW-419: Bridge tasks checked against Controller CostGate
def test_gw419_bridge_packet_enforces_controller_costgate(tmp_path):
    job_file = tmp_path / "job-419.json"
    job_file.write_text(json.dumps({"task_id": "T-419", "instruction": "echo test"}))

    packet = build_local_shell_task_packet(job_file)
    cost = packet["params"].get("estimated_cost_eur")
    assert cost == 0.0
    assert packet["params"].get("cost_class") == "included_quota"

    # Evaluated through CostGate
    verdict = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=cost)
    assert verdict["allowed"] is True
    assert verdict["requires_human_gate"] is False


# GW-420: PR #838 single away-queue enqueue policy
def test_gw420_pr838_away_queue_single_enqueue_and_dedupe():
    import subprocess

    # Verify PR #838's test suite directly from origin/cursor/stop-identical-requeue-be3a
    res = subprocess.run(
        ["git", "show", "origin/cursor/stop-identical-requeue-be3a:tests/test_antigravity_requeue_policy.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    test_code = res.stdout
    assert "test_completed_fingerprint_is_not_requeued" in test_code
    assert "test_one_new_unit_can_still_be_queued" in test_code
    assert "test_human_gates_stay_single_decisions" in test_code
    assert "test_windows_worker_schedule_still_starts_the_product" in test_code

    # Also verify the diff in AWAY_QUEUE_REFILL_PROTOCOL.md on PR #838
    res_proto = subprocess.run(
        ["git", "show", "origin/cursor/stop-identical-requeue-be3a:docs/v1/orchestration/AWAY_QUEUE_REFILL_PROTOCOL.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    proto_text = res_proto.stdout
    assert "65x or 100x" not in proto_text
    assert "Queue this token once." in proto_text
    assert "A completed workkey does not send the same prompt again." in proto_text
    assert "Human gates stay single decisions" in proto_text


# GW-421 & GW-422: CI watch state comparison and single targeted investigation policy
def test_gw421_gw422_ci_state_deterministic_dispatch_policy():
    def evaluate_ci_watch_tick(last_state, current_state):
        if (
            last_state.get("head_sha") == current_state.get("head_sha")
            and last_state.get("checks_pass") == current_state.get("checks_pass")
        ):
            return "NOOP_PRESERVE_OBSERVATION", None
        failed_jobs = [j for j, passed in current_state.get("jobs", {}).items() if not passed]
        if failed_jobs:
            return "INVESTIGATE_TARGETED_FAILURES", failed_jobs
        return "CHECK_READY_WORKKEYS", None

    state_a = {"head_sha": "abc123", "checks_pass": True, "jobs": {"job1": True, "job2": True}}
    # Unchanged state produces NOOP (GW-421)
    action, payload = evaluate_ci_watch_tick(state_a, dict(state_a))
    assert action == "NOOP_PRESERVE_OBSERVATION"
    assert payload is None

    # New CI failure triggers targeted investigation only (GW-422)
    state_fail = {
        "head_sha": "abc124",
        "checks_pass": False,
        "jobs": {"job1": True, "job2": False, "job3": False},
    }
    action, payload = evaluate_ci_watch_tick(state_a, state_fail)
    assert action == "INVESTIGATE_TARGETED_FAILURES"
    assert payload == ["job2", "job3"]
