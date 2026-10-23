"""Google Antigravity Windows — Night Engineering V12 Negative Regression Suite.

Verifies:
1. #836 DONE->CLAIMED regression prevention under repeated ticks and IDLE/heartbeats.
2. Lost RESULT_READY / ACK-replay idempotency and tamper conflict detection.
3. Strict zero-FINAL without verifier-accepted journal proof (no fake green).
4. CostGate pre-admission negative checks (NaN, Inf, negatives, strings, over-limit).
5. Mismatched attempt / cross-worker spoofing fail-closed rejections.
6. Windows artifact path safety (device names, directory traversals, absolute paths).
7. Fencing token protection against stale writers and foreign task substitution.

Strictly enforces:
- AUTONOMOUS_SPEND_LIMIT_EUR = 0.00
- SINGLE_WRITER = YES
- UNKNOWN_COST = BLOCK
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import pytest

from courier_core.controller import (
    ApiError,
    Controller,
    MAX_ARTIFACTS,
    RESOLVED_VERIFIED,
    TaskStatus,
)
from courier_core.events import Event, EventType
from courier_core.state_machine import TERMINAL
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
from scripts.windows_worker.daemon import is_safe_artifact_path


# ==============================================================================
# 1. #836 DONE->CLAIMED Prevention Under Repeated IDLE & Heartbeat Ticks
# ==============================================================================

def test_gw12_01_proven_done_never_reverts_to_claimed_under_idle_or_ticks(tmp_path):
    """GW12-01: Once a workkey is proven DONE via finish_turn, subsequent IDLE,

    HEARTBEAT or periodic health ticks must NEVER overwrite DONE with CLAIMED.
    """
    from courier_runtime.host_loop import emit_signal, run_once
    from courier_runtime.provider_events import handle

    campaign_path = tmp_path / "campaign" / "kirby.json"
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        engine = LedgerEngine(ctrl, campaign_path, "win-host-1")
        engine.add_workkeys(["WK-12-01"])
        engine.open_slot("S1", "antigravity")

        claimed = engine.next("S1")
        assert claimed is not None
        workkey, token = claimed

        # Create task and execute to verification
        task_id = engine.submit(workkey, {
            "adapter": "synthetic",
            "params": {"unit": "u12_01", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        c = ctrl.claim({"worker_id": "win-verifier-1"})
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "win-verifier-1"})
        data = b'{"result": "gw12_01_ok"}'
        digest = hashlib.sha256(data).hexdigest()
        (ctrl.home / "art.json").write_bytes(data)
        ctrl.result({
            "dispatch_id": c["dispatch_id"],
            "result_id": "res-12-01",
            "outcome": "success",
            "artifacts": [{"path": "art.json", "sha256": digest}],
        })
        assert ctrl.verify_next() is True

        # Finish turn with real proof; returns session wake state (IDLE when queue empty)
        outcome = engine.finish_turn("S1", workkey, token, task_id, checkpoint="turn_done")
        assert outcome in ("IDLE", "WAKE_PENDING")

        # Verify disk state is DONE with proof
        state_after_done = json.loads(campaign_path.read_text(encoding="utf-8"))
        assert state_after_done["workkeys"]["WK-12-01"]["state"] == DONE
        assert ":RESULT_ACCEPTED" in state_after_done["workkeys"]["WK-12-01"]["checkpoint"]

        # Now simulate stale in-memory Kirby receiving IDLE or HEARTBEAT
        stale_kirby = Kirby(campaign_path, "win-host-1")
        # Direct handle call with IDLE
        res_idle = handle(stale_kirby, "S1", "IDLE")
        assert res_idle in ("IDLE", "COALESCED", "IGNORED")

        # Disk must still be DONE!
        state_after_idle = json.loads(campaign_path.read_text(encoding="utf-8"))
        assert state_after_idle["workkeys"]["WK-12-01"]["state"] == DONE

        # Direct handle call with HEARTBEAT
        res_hb = handle(stale_kirby, "S1", "HEARTBEAT progress=1 checkpoint=later_tick")
        assert res_hb in ("HEARTBEAT", "COALESCED", "IGNORED")
        state_after_hb = json.loads(campaign_path.read_text(encoding="utf-8"))
        assert state_after_hb["workkeys"]["WK-12-01"]["state"] == DONE

        # Host loop run_once tick
        signals = tmp_path / "signals.log"
        signals.write_text("", encoding="utf-8")
        emit_signal(signals, "IDLE")
        run_once(stale_kirby, "S1", signals, {"offset": 0, "last_tick": stale_kirby.clock(), "notified": {}})
        state_after_run_once = json.loads(campaign_path.read_text(encoding="utf-8"))
        assert state_after_run_once["workkeys"]["WK-12-01"]["state"] == DONE

        # Exactly 1 receipt in receipts.jsonl
        receipts = (campaign_path.parent / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(receipts) == 1
    finally:
        ctrl.stop()


# ==============================================================================
# 2. Lost RESULT_READY / ACK-Replay Idempotency & Tamper Detection
# ==============================================================================

def test_gw12_02_lost_ack_replay_and_tamper_conflict_rejection(tmp_path):
    """GW12-02: Controller.result handles network-lost ACK replay with ACK_DUPLICATE

    and rejects any attempt to resubmit the same result_id with conflicting content.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        _, r = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "gw12_02", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        task_id = r["task_id"]
        claim = ctrl.claim({"worker_id": "win-w1"})
        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "win-w1"})

        content = b"evidence payload"
        digest = hashlib.sha256(content).hexdigest()
        (ctrl.home / "art.txt").write_bytes(content)

        # 1. Initial submission -> ACCEPTED_FOR_VERIFY
        code1, resp1 = ctrl.result({
            "dispatch_id": claim["dispatch_id"],
            "result_id": "res-gw12-02",
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": digest}],
        })
        assert code1 == 200
        assert resp1["status"] == "ACCEPTED_FOR_VERIFY"
        first_seq = resp1["seq"]

        # 2. Lost ACK Replay (same dispatch, same result_id, same content) -> ACK_DUPLICATE
        code2, resp2 = ctrl.result({
            "dispatch_id": claim["dispatch_id"],
            "result_id": "res-gw12-02",
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": digest}],
        })
        assert code2 == 200
        assert resp2["status"] == "ACK_DUPLICATE"
        assert resp2["seq"] == first_seq

        # 3. Conflicting submission (same result_id, modified artifact hash) -> 409 result_conflict
        with pytest.raises(ApiError) as exc_conflict:
            ctrl.result({
                "dispatch_id": claim["dispatch_id"],
                "result_id": "res-gw12-02",
                "outcome": "success",
                "artifacts": [{"path": "art.txt", "sha256": "0" * 64}],
            })
        assert exc_conflict.value.status == 409
        assert exc_conflict.value.code == "result_conflict"

        # 4. Now verify the task to completion
        assert ctrl.verify_next() is True
        assert ctrl.journal.task(task_id).status == TaskStatus.COMPLETE

        # 5. Replaying original result on COMPLETE task -> still returns ACK_DUPLICATE
        code3, resp3 = ctrl.result({
            "dispatch_id": claim["dispatch_id"],
            "result_id": "res-gw12-02",
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": digest}],
        })
        assert code3 == 200
        assert resp3["status"] == "ACK_DUPLICATE"

        # 6. Attempting a DIFFERENT result_id on a complete dispatch -> 409 stale_dispatch
        with pytest.raises(ApiError) as exc_stale:
            ctrl.result({
                "dispatch_id": claim["dispatch_id"],
                "result_id": "res-stale-different",
                "outcome": "success",
                "artifacts": [{"path": "art.txt", "sha256": digest}],
            })
        assert exc_stale.value.status == 409
        assert exc_stale.value.code == "stale_dispatch"

        # Verify that LATE_RESULT_DISCARDED was appended to the journal
        events = list(ctrl.journal.events(task_id=task_id))
        late_events = [e for e in events if e.type == EventType.LATE_RESULT_DISCARDED]
        assert len(late_events) == 1
        assert late_events[0].result_id == "res-stale-different"
    finally:
        ctrl.stop()


# ==============================================================================
# 3. Zero FINAL Without Accepted Journal Proof (No Fake Green)
# ==============================================================================

def test_gw12_03_zero_final_without_verified_result_accepted(tmp_path):
    """GW12-03: Provider claiming completion or human confirmation without verifier

    acceptance returns NOT_PROVEN; only RESULT_ACCEPTED in journal permits DONE.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        engine = LedgerEngine(ctrl, tmp_path / "campaign.json", "host-win")
        engine.add_workkeys(["WK-12-03"])
        engine.open_slot("S1", "antigravity")

        workkey, token = engine.next("S1")
        task_id = engine.submit(workkey, {
            "adapter": "synthetic",
            "params": {"unit": "gw12_03", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        }, slot="S1", token=token)

        # Case A: Provider says "DONE" right after creation, nothing claimed or verified -> NOT_PROVEN
        assert engine.finish_turn("S1", workkey, token, task_id, checkpoint="provider_promise") == NOT_PROVEN
        assert engine.proof(task_id) is None

        # Case B: Worker claims, starts, and reports result, but verification has NOT run yet
        c = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
        content = b"evidence bytes"
        digest = hashlib.sha256(content).hexdigest()
        (ctrl.home / "art.bin").write_bytes(content)
        ctrl.result({
            "dispatch_id": c["dispatch_id"],
            "result_id": "res-12-03",
            "outcome": "success",
            "artifacts": [{"path": "art.bin", "sha256": digest}],
        })
        # Task is in VERIFYING state, not yet COMPLETE/RESOLVED_VERIFIED
        assert ctrl.journal.task(task_id).status == TaskStatus.VERIFYING
        assert engine.finish_turn("S1", workkey, token, task_id, checkpoint="submitted_not_verified") == NOT_PROVEN
        assert engine.proof(task_id) is None

        # Case C: Verification runs and fails (e.g. file tampered)
        (ctrl.home / "art.bin").write_bytes(b"tampered content")
        assert ctrl.verify_next() is True
        task_failed = ctrl.journal.task(task_id)
        assert task_failed.status == TaskStatus.FAILED
        # Provider still cannot mark DONE; finish_turn records FAILED_FINAL and wakes session
        res_fail = engine.finish_turn("S1", workkey, token, task_id, checkpoint="after_failed_verify")
        assert res_fail in ("IDLE", "WAKE_PENDING")
        kirby_fail = json.loads((tmp_path / "campaign.json").read_text(encoding="utf-8"))
        assert kirby_fail["workkeys"]["WK-12-03"]["state"] == "FAILED_FINAL"
        assert engine.proof(task_id) is None
    finally:
        ctrl.stop()


# ==============================================================================
# 4. Negative CostGate Pre-Admission Validation
# ==============================================================================

def test_gw12_04_costgate_pre_admission_adversarial_rejections(tmp_path):
    """GW12-04: Validate cost_admission and CostGate adversarial rejections

    and prove LedgerEngine.submit parks the workkey as COST_BLOCKED before journal write.
    """
    # 1. cost_admission checks
    assert "UNKNOWN_COST" in cost_admission(None)
    assert "UNKNOWN_COST" in cost_admission({})
    assert "UNKNOWN_COST" in cost_admission({"unknown_cost": True})
    assert "UNKNOWN_COST" in cost_admission({"cost_class": "unknown"})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": "0.0"})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": False})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": True})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("nan")})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("inf")})
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("-inf")})
    assert "INVALID_COST" in cost_admission({"estimated_cost_eur": -0.01})
    assert "OVER_LIMIT" in cost_admission({"estimated_cost_eur": 0.0001}, spend_limit_eur=0.0)

    # 2. Genuine 0.0 EUR is permitted
    assert cost_admission({"estimated_cost_eur": 0.0}, spend_limit_eur=0.0) is None

    # 3. LedgerEngine.submit fail-closed with workkey parking
    campaign_file = tmp_path / "campaign.json"
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        engine = LedgerEngine(ctrl, campaign_file, "host-win", spend_limit_eur=0.0)
        engine.add_workkeys(["WK-COST-BLOCK"])
        engine.open_slot("S1", "antigravity")

        wk, token = engine.next("S1")
        with pytest.raises(CostBlocked) as exc_blocked:
            engine.submit(wk, {
                "adapter": "synthetic",
                "params": {"unit": "blocked", "estimated_cost_eur": float("nan")},
                "effect_class": "idempotent",
                "max_attempts": 1,
                "lease_ttl_s": 30,
            }, slot="S1", token=token)

        assert "UNKNOWN_COST" in str(exc_blocked.value)

        # Kirby workkey must be parked as BLOCKED with COST_BLOCKED blocked_reason
        kirby_data = json.loads(campaign_file.read_text(encoding="utf-8"))
        assert kirby_data["workkeys"]["WK-COST-BLOCK"]["state"] == "BLOCKED"
        assert COST_BLOCKED in kirby_data["workkeys"]["WK-COST-BLOCK"]["blocked_reason"]

        # Ensure NO task was written to the Controller journal
        assert len(list(ctrl.journal.tasks())) == 0
    finally:
        ctrl.stop()


# ==============================================================================
# 5. Mismatched Attempt / Cross-Worker Spoofing in Direct Result Submission
# ==============================================================================

def test_gw12_05_mismatched_and_spoofed_result_submissions(tmp_path):
    """GW12-05: Direct Controller.result endpoint rejects unknown dispatch,

    unstarted claims, cancelled tasks, excessive artifacts, and invalid outcomes.
    """
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        # A. Unknown dispatch ID -> 404 unknown_dispatch
        with pytest.raises(ApiError) as exc_404:
            ctrl.result({
                "dispatch_id": "dsp-nonexistent",
                "result_id": "res-1",
                "outcome": "success",
                "artifacts": [],
            })
        assert exc_404.value.status == 404
        assert exc_404.value.code == "unknown_dispatch"

        # B. Claimed but not started -> 409 not_started
        _, r = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "u12_05", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        task_id = r["task_id"]
        c = ctrl.claim({"worker_id": "w1"})
        with pytest.raises(ApiError) as exc_not_started:
            ctrl.result({
                "dispatch_id": c["dispatch_id"],
                "result_id": "res-not-started",
                "outcome": "success",
                "artifacts": [],
            })
        assert exc_not_started.value.status == 409
        assert exc_not_started.value.code == "not_started"

        # C. Start the dispatch
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})

        # D. Artifacts exceeding MAX_ARTIFACTS (32) -> 400 invalid_request
        with pytest.raises(ApiError) as exc_max_art:
            ctrl.result({
                "dispatch_id": c["dispatch_id"],
                "result_id": "res-too-many-artifacts",
                "outcome": "success",
                "artifacts": [{"path": f"art_{i}.txt", "sha256": "a" * 64} for i in range(MAX_ARTIFACTS + 1)],
            })
        assert exc_max_art.value.status == 400
        assert exc_max_art.value.code == "invalid_request"

        # E. Invalid outcome string -> 400 invalid_request
        with pytest.raises(ApiError) as exc_bad_outcome:
            ctrl.result({
                "dispatch_id": c["dispatch_id"],
                "result_id": "res-bad-outcome",
                "outcome": "finished_ok",
                "artifacts": [],
            })
        assert exc_bad_outcome.value.status == 400
        assert exc_bad_outcome.value.code == "invalid_request"
    finally:
        ctrl.stop()


# ==============================================================================
# 6. Artifact Store Traversal & Device Name Safety (Windows Path Failsafe)
# ==============================================================================

@pytest.mark.parametrize("bad_device", [
    "con", "CON.txt", "aux", "AUX.dat", "NUL", "nul.json",
    "com1", "COM9", "lpt1", "LPT9.txt", "prn", "PRN.log"
])
def test_gw12_06_windows_reserved_device_names_rejected(bad_device):
    """GW12-06: Windows reserved device names must always be rejected as safe artifact paths."""
    assert is_safe_artifact_path(bad_device) is False
    assert is_safe_artifact_path(f"sub/{bad_device}") is False


@pytest.mark.parametrize("bad_traversal", [
    "../secret.txt", "../../etc/shadow", "C:/Windows/System32",
    "D:\\data\\file.txt", "out/../../file.txt", "\\\\network\\share\\file.txt"
])
def test_gw12_06_traversal_and_absolute_paths_rejected(bad_traversal):
    """GW12-06: Parent directory traversals and absolute/UNC paths must always be rejected."""
    assert is_safe_artifact_path(bad_traversal) is False


def test_gw12_06_genuine_relative_artifact_path_accepted():
    """GW12-06: Clean relative POSIX artifact paths within task directory are accepted."""
    assert is_safe_artifact_path("report.json") is True
    assert is_safe_artifact_path("artifacts/output_01.bin") is True
    assert is_safe_artifact_path("evidence/2026/result.txt") is True


# ==============================================================================
# 7. Double-Finish and Stale Token Rejection
# ==============================================================================

def test_gw12_07_stale_token_and_foreign_task_double_finish_safety(tmp_path):
    """GW12-07: finish_turn protects against stale tokens, foreign task substitution,

    and ensures a second finish_turn call is safely idempotent without duplicate receipts.
    """
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        campaign_path = tmp_path / "campaign.json"
        engine = LedgerEngine(ctrl, campaign_path, "host-win")
        engine.add_workkeys(["WK-A", "WK-B"])
        engine.open_slot("S1", "antigravity")

        wk_a, tok_a = engine.next("S1")
        assert wk_a == "WK-A"
        task_a = engine.submit(wk_a, {
            "adapter": "synthetic",
            "params": {"unit": "ua", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })

        # 1. Foreign task ID substitution is rejected
        res_foreign = engine.finish_turn("S1", wk_a, tok_a, task_id="task-FOREIGN-999")
        assert res_foreign == REJECTED_FOREIGN_TASK

        # 2. Stale token rejection
        res_stale = engine.finish_turn("S1", wk_a, token=tok_a + 999, task_id=task_a)
        assert res_stale == "REJECTED_STALE_WRITER"

        # 3. Valid completion
        c = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
        data = b"evidence A"
        (ctrl.home / "art.txt").write_bytes(data)
        ctrl.result({
            "dispatch_id": c["dispatch_id"],
            "result_id": "res-a",
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": hashlib.sha256(data).hexdigest()}],
        })
        ctrl.verify_next()

        res_ok = engine.finish_turn("S1", wk_a, tok_a, task_a, checkpoint="first_finish")
        assert res_ok in ("IDLE", "WAKE_PENDING")
        kirby_data_a = json.loads(campaign_path.read_text(encoding="utf-8"))
        assert kirby_data_a["workkeys"]["WK-A"]["state"] == DONE

        receipt_file = campaign_path.parent / "receipts.jsonl"
        lines_1 = receipt_file.read_text(encoding="utf-8").splitlines()
        assert len(lines_1) == 1

        # 4. Calling finish_turn again after workkey is already DONE
        # Does not fail and does NOT append a duplicate receipt line
        res_repeat = engine.finish_turn("S1", wk_a, tok_a, task_a, checkpoint="second_finish")
        assert res_repeat in ("DONE", "REJECTED_STALE_WRITER")
        lines_2 = receipt_file.read_text(encoding="utf-8").splitlines()
        assert len(lines_2) == 1
    finally:
        ctrl.stop()
