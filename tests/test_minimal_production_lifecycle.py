"""TEST ONLY failure courts for the production lifecycle trust boundary."""

import datetime
import hashlib
import json
import time

import pytest

import scripts.run_live_production_goal as runtime
from scripts.opportunity_queue import Opportunity, OpportunityQueue


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def add_opportunity(root, task_id="TASK", status="READY", scope=None, description=None):
    queue = OpportunityQueue(repo_dir=root)
    opportunity = Opportunity(
        opportunity_id=task_id,
        source="TEST_ONLY",
        objective_id="ROOT",
        project="Courier",
        description=description or task_id,
        status=status,
        target_agent="GEMINI",
        allowed_scope=scope or ["work/output.txt"],
        allowed_actions=["implement_bounded_improvement"],
    )
    assert queue.add_opportunity(opportunity)
    return queue, opportunity


def install_verified_external_result(root, queue, opportunity, claim, *, provenance=None):
    artifact = root / "work" / "output.txt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(b"before").hexdigest()
    artifact.write_text("after", encoding="utf-8")
    request_id = "REQ-MAC-LIFECYCLE"
    task_hash = "task-hash"
    expected_provenance = runtime.opportunity_provenance(opportunity)
    actual_provenance = provenance or expected_provenance
    lease = {
        "claim_id": claim["claim_id"],
        "generation": claim["state_version"],
        "owner": claim["claim_owner"],
        "expires_at": claim["lease_expires_at"],
    }
    request = {
        "task_id": opportunity.opportunity_id,
        "task_hash": task_hash,
        "target_agent": "GEMINI",
        "provenance": expected_provenance,
        "lease": lease,
        "pre_effect_fingerprints": {"work/output.txt": before},
        "payload": {"allowed_scope": opportunity.allowed_scope},
    }
    payload = {
        "task_id": opportunity.opportunity_id,
        "task_hash": task_hash,
        "target_agent": "GEMINI",
        "verdict": "PASS",
        "changed_files": ["work/output.txt"],
    }
    observed = "PAYLOAD_SHA256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    fingerprint = hashlib.sha256(f"{request_id}COMPLETED{observed}".encode()).hexdigest()
    result = {
        "request_id": request_id,
        "mission_id": opportunity.opportunity_id,
        "schema_version": "1.0",
        "status": "COMPLETED",
        "observed_behavior": observed,
        "result_fingerprint": fingerprint,
        "provenance": actual_provenance,
        "lease": lease,
        "payload": payload,
    }
    ack = {"request_id": request_id, "fingerprint": fingerprint}
    write_json(root / "coordination" / "local_requests" / f"{request_id}.json", request)
    write_json(root / "coordination" / "windows_to_mac" / "results" / f"{request_id}.json", result)
    write_json(root / "coordination" / "mac_to_windows" / "acks" / f"{request_id}.ack.json", ack)


def test_unverified_result_cannot_advance_state(tmp_path, monkeypatch):
    queue, _ = add_opportunity(tmp_path, "FORGED")
    write_json(tmp_path / "events" / "results" / "forged.json", {"task_id": "FORGED", "status": "COMPLETED"})
    monkeypatch.setattr(runtime, "COURIER_DIR", tmp_path)
    runtime.update_completed_tasks()
    assert OpportunityQueue(tmp_path).get_opportunity("FORGED").status == "READY"


def test_customs_precedes_terminal_transition_and_duplicate_is_idempotent(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "output.txt").write_text("before", encoding="utf-8")
    queue, opportunity = add_opportunity(tmp_path)
    claimed, _, claim = queue.claim_opportunity("TASK", "GEMINI", lease_seconds=60)
    assert claimed
    assert queue.mark_claim_dispatch_state("TASK", claim["claim_id"], claim["state_version"], "DISPATCHING")
    assert queue.mark_claim_dispatch_state("TASK", claim["claim_id"], claim["state_version"], "DISPATCHED")
    install_verified_external_result(tmp_path, queue, opportunity, claim)
    monkeypatch.setattr(runtime, "COURIER_DIR", tmp_path)
    first = runtime.update_completed_tasks()
    assert any(item["status"] == "RESULT_RECONCILED" for item in first)
    assert OpportunityQueue(tmp_path).get_opportunity("TASK").status == "COMPLETED"
    second = runtime.update_completed_tasks()
    assert not [item for item in second if item.get("status") == "RESULT_RECONCILED"]
    assert OpportunityQueue(tmp_path).get_opportunity("TASK").status == "COMPLETED"


def test_wrong_provenance_and_human_gate_fail_closed(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "output.txt").write_text("before", encoding="utf-8")
    queue, opportunity = add_opportunity(tmp_path, "PROVENANCE")
    claimed, _, claim = queue.claim_opportunity("PROVENANCE", "GEMINI", lease_seconds=60)
    assert claimed
    install_verified_external_result(tmp_path, queue, opportunity, claim, provenance={"source_hash": "forged"})
    gate_queue, _ = add_opportunity(tmp_path, "GATE", status="WAITING_FOR_HUMAN", description="gate")
    write_json(tmp_path / "events" / "results" / "gate.json", {"task_id": "GATE", "status": "COMPLETED"})
    monkeypatch.setattr(runtime, "COURIER_DIR", tmp_path)
    runtime.update_completed_tasks()
    refreshed = OpportunityQueue(tmp_path)
    assert refreshed.get_opportunity("PROVENANCE").status == "RUNNING"
    assert refreshed.get_opportunity("GATE").status == "WAITING_FOR_HUMAN"


def test_codex_bridge_result_requires_independently_observed_effect(tmp_path, monkeypatch):
    artifact = tmp_path / "work" / "codex.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("before", encoding="utf-8")
    queue, opportunity = add_opportunity(tmp_path, "CODEX-TASK", scope=["work/codex.txt"])
    opportunity.target_agent = "CODEX"
    queue.save_opportunity(opportunity)
    claimed, _, claim = queue.claim_opportunity("CODEX-TASK", "CODEX", lease_seconds=60)
    assert claimed
    assert queue.mark_claim_dispatch_state("CODEX-TASK", claim["claim_id"], claim["state_version"], "DISPATCHING")
    assert queue.mark_claim_dispatch_state("CODEX-TASK", claim["claim_id"], claim["state_version"], "DISPATCHED")
    artifact.write_text("after", encoding="utf-8")
    opportunity = queue.get_opportunity("CODEX-TASK")
    provenance = {
        "origin": opportunity.source,
        "task_identity": "CODEX-TASK",
        "source_artifact": "events/receipts/CODEX-TASK-receipt.json",
        "source_sha256": "receipt-hash",
        "opportunity": runtime.opportunity_provenance(opportunity),
        "opportunity_lease": {
            "claim_id": claim["claim_id"],
            "generation": claim["state_version"],
            "owner": claim["claim_owner"],
            "expires_at": claim["lease_expires_at"],
        },
    }
    job = {
        "task_id": "CODEX-TASK",
        "task_hash": "codex-task-hash",
        "scope": ["work/codex.txt"],
        "provenance": provenance,
        "pre_effect_fingerprints": {"work/codex.txt": hashlib.sha256(b"before").hexdigest()},
    }
    payload = {
        "verdict": "PASS",
        "task_id": "CODEX-TASK",
        "task_hash": "codex-task-hash",
        "target_agent": "CODEX",
        "changed_files": ["work/codex.txt"],
    }
    result = {
        "task_id": "CODEX-TASK",
        "status": "COMPLETED",
        "payload": payload,
        "payload_hash": runtime.stable_hash(payload),
        "provenance": provenance,
    }
    write_json(tmp_path / "events" / "processed" / "CODEX-TASK-worker-job.json", job)
    write_json(tmp_path / "events" / "processed" / "CODEX-TASK-result.json", result)
    monkeypatch.setattr(runtime, "COURIER_DIR", tmp_path)
    runtime.update_completed_tasks()
    assert OpportunityQueue(tmp_path).get_opportunity("CODEX-TASK").status == "COMPLETED"


def test_stale_claim_requeues_only_before_dispatch_and_quarantines_unknown_effect(tmp_path):
    queue, _ = add_opportunity(tmp_path, "PRE")
    claimed, _, _ = queue.claim_opportunity("PRE", "GEMINI", lease_seconds=-1)
    assert claimed
    recovered = OpportunityQueue(tmp_path).recover_expired_claims()
    assert recovered[0]["status"] == "PRE_DISPATCH_REQUEUED"
    assert OpportunityQueue(tmp_path).get_opportunity("PRE").status == "READY"

    queue, _ = add_opportunity(tmp_path, "UNKNOWN")
    claimed, _, claim = queue.claim_opportunity("UNKNOWN", "GEMINI", lease_seconds=1)
    assert claimed
    assert queue.mark_claim_dispatch_state("UNKNOWN", claim["claim_id"], claim["state_version"], "DISPATCHING")
    assert queue.mark_claim_dispatch_state("UNKNOWN", claim["claim_id"], claim["state_version"], "DISPATCHED")
    time.sleep(1.1)
    recovered = OpportunityQueue(tmp_path).recover_expired_claims()
    assert recovered[0]["status"] == "UNKNOWN_EFFECT_QUARANTINED"
    assert OpportunityQueue(tmp_path).get_opportunity("UNKNOWN").status == "BLOCKED"


def test_pre_execution_retry_is_bounded(tmp_path):
    queue, _ = add_opportunity(tmp_path, "RETRY")
    outcomes = []
    for _ in range(3):
        claimed, _, claim = queue.claim_opportunity("RETRY", "GEMINI", lease_seconds=60)
        assert claimed
        assert queue.mark_claim_dispatch_state("RETRY", claim["claim_id"], claim["state_version"], "DISPATCHING")
        outcomes.append(queue.resolve_pre_execution_failure("RETRY", claim["claim_id"], claim["state_version"], 3))
        queue = OpportunityQueue(tmp_path)
    assert outcomes == ["RETRYABLE", "RETRYABLE", "RETRY_BUDGET_EXHAUSTED"]
    assert queue.get_opportunity("RETRY").status == "BLOCKED"


def test_ready_and_active_limits_are_hard(tmp_path):
    queue = OpportunityQueue(tmp_path)
    for index in range(6):
        assert queue.add_opportunity(Opportunity(
            opportunity_id=f"T{index}", source="TEST_ONLY", objective_id="ROOT",
            project="Courier", description=f"task {index}", target_agent="GEMINI",
            allowed_scope=[f"work/{index}.txt"],
        ))
    assert len(queue.list_opportunities("READY")) == 5
    assert len(queue.list_opportunities("DEFERRED")) == 1

    recommendations = {
        "A": {"recommended_action": "DISPATCH_TASK_T0", "task_fingerprint": "a", "scope": ["work/0.txt"]},
        "B": {"recommended_action": "DISPATCH_TASK_T1", "task_fingerprint": "b", "scope": ["work/1.txt"]},
    }
    calls = []
    active, count = runtime.dispatch_recommendations(
        recommendations, queue, "goal", set(), dispatch_fn=lambda *args: calls.append(args) or True
    )
    assert active is True and count == 1 and len(calls) == 1
    assert len([item for item in OpportunityQueue(tmp_path).list_opportunities() if item.status == "RUNNING"]) == 1


def test_reconcile_demotes_preexisting_ready_overflow(tmp_path):
    queue = OpportunityQueue(tmp_path)
    for index in range(7):
        opportunity = Opportunity(
            opportunity_id=f"LEGACY-{index}", source="TEST_ONLY", objective_id="ROOT",
            project="Courier", description=f"legacy task {index}", target_agent="GEMINI",
            allowed_scope=[f"work/{index}.txt"],
        )
        queue.opportunities[opportunity.opportunity_id] = opportunity
        queue.save_opportunity(opportunity)

    queue.promote_deferred(ready_limit=5)

    assert len(queue.list_opportunities("READY")) == 5
    assert len(queue.list_opportunities("DEFERRED")) == 2


def test_atomic_json_failure_leaves_old_canonical_state(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    runtime.atomic_write_json(target, {"state": "old"})
    real_replace = runtime.os.replace

    def fail_publish(_source, _target):
        raise OSError("TEST ONLY injected publish failure")

    monkeypatch.setattr(runtime.os, "replace", fail_publish)
    try:
        try:
            runtime.atomic_write_json(target, {"state": "new"})
        except OSError:
            pass
    finally:
        monkeypatch.setattr(runtime.os, "replace", real_replace)
    assert json.loads(target.read_text()) == {"state": "old"}


def test_corrupt_authoritative_queue_state_fails_closed(tmp_path):
    queue_dir = tmp_path / "events" / "opportunity-queue"
    queue_dir.mkdir(parents=True)
    (queue_dir / "BROKEN.json").write_text('{"opportunity_id":', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Corrupt authoritative opportunity state"):
        OpportunityQueue(tmp_path)
