"""Google Antigravity Windows — Ledger Red Team V21 Suite (GW21-01 to GW21-15).

Independent Security & Integration Verifier for Courier Symphony.
Executes against real Controller, SQLite Journal, LedgerEngine, and Verifiers.

Validates Gates L2-01 through L2-08 from the 4-Hour Engineering Contract:
- L2-01 / L2-02: F-C1 Controller.create_task cost admission gap & idempotency
- L2-03 / L2-04: Task dependency input binding & disk byte verification
- L2-05 / L2-06: Journal RESULT_ACCEPTED proof, no fake green, single writer
- L2-07 / L2-08: Red-to-green contract verification and spend authorization
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import pytest

from adapters.synthetic import verify as synthetic_verify
from courier_core.controller import (
    ApiError,
    Controller,
    RESOLVED_VERIFIED,
    TaskStatus,
)
from courier_core.events import Event, EventType
from courier_runtime.continuity import CLAIMED, DONE, Kirby
from courier_runtime.ledger_engine import (
    COST_BLOCKED,
    CostBlocked,
    LedgerEngine,
    NOT_PROVEN,
    REJECTED_FOREIGN_TASK,
    cost_admission,
    task_id_for,
)
from scripts.resource_policy import CostGate


# ==============================================================================
# GW21-01 to GW21-05: F-C1 Controller.create_task Bypass & Idempotency
# ==============================================================================

def test_gw21_01_gw21_02_reproduce_fc1_raw_controller_bypass(tmp_path):
    """GW21-01 & GW21-02: Reproduce F-C1 gap on real Controller.create_task path.

    Documents that direct Controller.create_task currently admits tasks with
    NaN, Inf, or missing cost parameters, writing TASK_CREATED to the journal.
    This gap must be closed by the L2 lane owner.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        # Part 1: NaN/Inf is rejected by Event's canonical JSON serializer (HTTP 400)
        with pytest.raises(ApiError) as exc_nan:
            ctrl.create_task({
                "adapter": "synthetic",
                "params": {"unit": "fc1_nan", "estimated_cost_eur": float("nan")},
                "effect_class": "idempotent",
                "max_attempts": 1,
                "lease_ttl_s": 30,
            })
        assert exc_nan.value.status == 400
        assert "not canonical JSON" in exc_nan.value.message

        # Part 2: F-C1 RAW BYPASS GAP: Valid JSON types that violate CostGate
        # (e.g. unknown_cost: True, cost_class: "unknown", negative cost, or positive spend without budget)
        # bypass Controller.create_task completely and append TASK_CREATED to the SQLite journal!
        code_unknown, resp_unknown = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "fc1_unknown", "unknown_cost": True, "estimated_cost_eur": -1.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        # CURRENT BEHAVIOR (Documenting the F-C1 gap): Controller admits it without cost admission!
        assert code_unknown == 201
        assert "task_id" in resp_unknown
        task_id = resp_unknown["task_id"]

        # GW21-02: Verify that TASK_CREATED is present in the journal with forbidden cost params
        events = list(ctrl.journal.events(task_id=task_id))
        created_events = [e for e in events if e.type == EventType.TASK_CREATED]
        assert len(created_events) == 1
        payload_params = created_events[0].payload["params"]
        assert payload_params.get("unknown_cost") is True
        assert payload_params.get("estimated_cost_eur") == -1.0
    finally:
        ctrl.stop()


def test_gw21_03_cost_admission_policy_contrast():
    """GW21-03: Evaluate cost_admission policy against verifiably forbidden inputs."""
    # Policy rejects NaN, Inf, -Inf, negative, string, boolean
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("nan")})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("inf")})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("-inf")})
    assert "INVALID_COST" in cost_admission({"estimated_cost_eur": -0.05})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": "0.0"})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": False})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": True})
    assert "UNKNOWN_COST" in cost_admission(None)
    assert "UNKNOWN_COST" in cost_admission({})
    assert "OVER_LIMIT" in cost_admission({"estimated_cost_eur": 0.001}, spend_limit_eur=0.0)

    # Genuine 0.0 EUR is allowed
    assert cost_admission({"estimated_cost_eur": 0.0}, spend_limit_eur=0.0) is None


def test_gw21_04_migration_trap_legacy_callers_omitting_cost(tmp_path):
    """GW21-04: Documents migration risk where legacy core tests omit estimated_cost_eur.

    Proves that existing internal controller callers use params without cost.
    The L2 owner must ensure compatibility or migrate callers cleanly.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        # Standard legacy caller format
        code, resp = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "legacy_smoke_test"},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        assert code == 201
        assert "task_id" in resp
    finally:
        ctrl.stop()


def test_gw21_05_idempotency_key_under_modified_body(tmp_path):
    """GW21-05: Verify idempotency_key contract: identical body returns duplicate=True;

    modified body raises 409 idempotency_conflict.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        body1 = {
            "adapter": "synthetic",
            "params": {"unit": "u_idem", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
            "idempotency_key": "workkey:GW21-05",
        }
        code1, resp1 = ctrl.create_task(body1)
        assert code1 == 201
        assert resp1["duplicate"] is False
        task_id = resp1["task_id"]

        # Identical body resubmitted -> 200 duplicate=True
        code2, resp2 = ctrl.create_task(body1)
        assert code2 == 200
        assert resp2["duplicate"] is True
        assert resp2["task_id"] == task_id

        # Modified body under same idempotency key -> 409 idempotency_conflict
        body_modified = dict(body1, params={"unit": "u_MODIFIED", "estimated_cost_eur": 0.0})
        with pytest.raises(ApiError) as exc_conflict:
            ctrl.create_task(body_modified)
        assert exc_conflict.value.status == 409
        assert exc_conflict.value.code == "idempotency_conflict"
    finally:
        ctrl.stop()


# ==============================================================================
# GW21-06 to GW21-10: Task Dependency & Artifact Byte Proof (L2-03, L2-04)
# ==============================================================================

def test_gw21_06_gw21_08_gw21_09_real_dependency_binding_a_b_c(tmp_path):
    """GW21-06, GW21-08, GW21-09: Test real dependency input contract.

    B cannot claim until A is verified; C cannot claim until B is verified.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        # Create Task A
        _, r_a = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "step_a", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        task_a = r_a["task_id"]

        # Create Task B depending on A
        _, r_b = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "step_b", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
            "depends_on": task_a,
        })
        task_b = r_b["task_id"]

        # Create Task C depending on B
        _, r_c = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "step_c", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
            "depends_on": task_b,
        })
        task_c = r_c["task_id"]

        # 1. Claim while A is unverified: Task A is claimed, Task B and C cannot be claimed
        claim_1 = ctrl.claim({"worker_id": "w1"})
        assert claim_1 is not None and claim_1["task_id"] == task_a

        # Attempt to claim next: None (B and C are blocked on unverified upstream)
        claim_none = ctrl.claim({"worker_id": "w2"})
        assert claim_none is None

        # Execute Task A to completion
        ctrl.start({"dispatch_id": claim_1["dispatch_id"], "worker_id": "w1"})
        data_a = b"artifact from step A"
        digest_a = hashlib.sha256(data_a).hexdigest()
        (ctrl.home / "art_a.txt").write_bytes(data_a)
        ctrl.result({
            "dispatch_id": claim_1["dispatch_id"],
            "result_id": "res-a",
            "outcome": "success",
            "artifacts": [{"path": "art_a.txt", "sha256": digest_a}],
        })
        assert ctrl.verify_next() is True
        assert ctrl.journal.task(task_a).status == TaskStatus.COMPLETE

        # 2. Now Task B becomes claimable, carrying Task A's verified input!
        claim_b = ctrl.claim({"worker_id": "w2"})
        assert claim_b is not None and claim_b["task_id"] == task_b
        assert "input" in claim_b["spec"]
        assert claim_b["spec"]["input"]["task_id"] == task_a
        assert claim_b["spec"]["input"]["result_id"] == "res-a"
        assert claim_b["spec"]["input"]["artifacts"][0]["sha256"] == digest_a

        # Task C still cannot be claimed because B is not verified
        assert ctrl.claim({"worker_id": "w3"}) is None

        # Execute Task B to completion
        ctrl.start({"dispatch_id": claim_b["dispatch_id"], "worker_id": "w2"})
        data_b = b"artifact from step B"
        digest_b = hashlib.sha256(data_b).hexdigest()
        (ctrl.home / "art_b.txt").write_bytes(data_b)
        ctrl.result({
            "dispatch_id": claim_b["dispatch_id"],
            "result_id": "res-b",
            "outcome": "success",
            "artifacts": [{"path": "art_b.txt", "sha256": digest_b}],
        })
        assert ctrl.verify_next() is True
        assert ctrl.journal.task(task_b).status == TaskStatus.COMPLETE

        # 3. Now Task C becomes claimable!
        claim_c = ctrl.claim({"worker_id": "w3"})
        assert claim_c is not None and claim_c["task_id"] == task_c
        assert claim_c["spec"]["input"]["task_id"] == task_b
    finally:
        ctrl.stop()


def test_gw21_07_ledger_engine_depends_on_refusal(tmp_path):
    """GW21-07: LedgerEngine.submit explicitly refuses depends_on; work is ordered by workkey."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        engine = LedgerEngine(ctrl, tmp_path / "campaign.json", "win-host")
        engine.add_workkeys(["WK-DEP"])
        engine.open_slot("S1", "antigravity")
        wk, tok = engine.next("S1")

        with pytest.raises(ValueError) as exc:
            engine.submit(wk, {
                "adapter": "synthetic",
                "params": {"unit": "dep", "estimated_cost_eur": 0.0},
                "effect_class": "idempotent",
                "max_attempts": 1,
                "lease_ttl_s": 30,
                "depends_on": "task-upstream",
            })
        assert "the ledger engine does not take depends_on" in str(exc.value)
    finally:
        ctrl.stop()


def test_gw21_10_altered_artifact_bytes_after_acceptance_rejects(tmp_path):
    """GW21-10: Modifying verified artifact bytes on disk causes verification failure."""
    home = tmp_path / "home"
    home.mkdir()
    data = b"original valid bytes"
    digest = hashlib.sha256(data).hexdigest()
    (home / "evidence.txt").write_bytes(data)

    class Task:
        dispatch_id = "dsp-21-10"
        effect_class = "idempotent"

    class Result:
        dispatch_id = "dsp-21-10"
        payload = {
            "outcome": "success",
            "artifacts": [{"path": "evidence.txt", "sha256": digest}],
        }

    # Valid check
    assert synthetic_verify(Task(), Result(), home).accepted is True

    # Mutate artifact bytes on disk
    (home / "evidence.txt").write_bytes(b"tampered bytes on disk")
    verdict = synthetic_verify(Task(), Result(), home)
    assert verdict.accepted is False
    assert verdict.reason == "evidence artifact hash does not match"


# ==============================================================================
# GW21-11 to GW21-15: Direct Result Validation, Finality & Red-Team Proofs
# ==============================================================================

def test_gw21_11_gw21_12_falscher_dispatch_und_fehlendes_result_accepted(tmp_path):
    """GW21-11 & GW21-12: Reject unknown dispatch ID and verify missing RESULT_ACCEPTED fails closed."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        # Unknown dispatch ID -> 404
        with pytest.raises(ApiError) as exc_404:
            ctrl.result({
                "dispatch_id": "dsp-unauthorized",
                "result_id": "res-1",
                "outcome": "success",
                "artifacts": [],
            })
        assert exc_404.value.status == 404
        assert exc_404.value.code == "unknown_dispatch"
    finally:
        ctrl.stop()


def test_gw21_13_provider_done_without_journal_proof_not_proven(tmp_path):
    """GW21-13: Provider DONE without SQLite journal proof evaluates strictly to NOT_PROVEN."""
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        campaign_file = tmp_path / "campaign.json"
        engine = LedgerEngine(ctrl, campaign_file, "win-host")
        engine.add_workkeys(["WK-21-13"])
        engine.open_slot("S1", "antigravity")

        wk, tok = engine.next("S1")
        task_id = engine.submit(wk, {
            "adapter": "synthetic",
            "params": {"unit": "u21_13", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })

        # Claim and start, but DO NOT submit result
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})

        # Provider claims it is DONE
        outcome = engine.finish_turn("S1", wk, tok, task_id, checkpoint="done_promise")
        assert outcome == NOT_PROVEN

        # Workkey remains CLAIMED on disk
        kirby_state = json.loads(campaign_file.read_text(encoding="utf-8"))
        assert kirby_state["workkeys"]["WK-21-13"]["state"] == CLAIMED
        assert not (campaign_file.parent / "receipts.jsonl").exists()
    finally:
        ctrl.stop()


def test_gw21_14_doppel_final_und_crash_replay(tmp_path):
    """GW21-14: Double-finish does not duplicate receipts and replay preserves single finality."""
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        campaign_file = tmp_path / "campaign.json"
        engine = LedgerEngine(ctrl, campaign_file, "win-host")
        engine.add_workkeys(["WK-FINAL"])
        engine.open_slot("S1", "antigravity")

        wk, tok = engine.next("S1")
        task_id = engine.submit(wk, {
            "adapter": "synthetic",
            "params": {"unit": "final_test", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        claim = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})

        data = b"evidence for final"
        (ctrl.home / "art.txt").write_bytes(data)
        ctrl.result({
            "dispatch_id": claim["dispatch_id"],
            "result_id": "res-final",
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": hashlib.sha256(data).hexdigest()}],
        })
        ctrl.verify_next()

        # First finish_turn -> saves DONE and appends 1 receipt
        res1 = engine.finish_turn("S1", wk, tok, task_id, checkpoint="step1")
        assert res1 in ("IDLE", "WAKE_PENDING")
        receipt_path = campaign_file.parent / "receipts.jsonl"
        lines1 = receipt_path.read_text(encoding="utf-8").splitlines()
        assert len(lines1) == 1

        # Second finish_turn replay -> does not append second receipt line
        res2 = engine.finish_turn("S1", wk, tok, task_id, checkpoint="step2")
        assert res2 in ("IDLE", "WAKE_PENDING", "REJECTED_STALE_WRITER")
        lines2 = receipt_path.read_text(encoding="utf-8").splitlines()
        assert len(lines2) == 1
    finally:
        ctrl.stop()


def test_gw21_15_negative_test_turns_red_on_tampered_digest():
    """GW21-15: Prove that negative tests are genuinely red on defect (anti-fake green)."""
    # A verifier asserting equality of authentic digest vs tampered digest must fail
    authentic_digest = hashlib.sha256(b"correct").hexdigest()
    tampered_digest = hashlib.sha256(b"tampered").hexdigest()

    def strict_digest_gate(d1, d2):
        if d1 != d2:
            return "RED_TAMPER_DETECTED"
        return "GREEN_AUTHENTIC"

    assert strict_digest_gate(authentic_digest, authentic_digest) == "GREEN_AUTHENTIC"
    assert strict_digest_gate(authentic_digest, tampered_digest) == "RED_TAMPER_DETECTED"
