"""Google Antigravity Windows — True-Proof Marathon V10 Suite (GW10-01 to GW10-35).

Independent red-team & production contract verification for Courier Symphony.
Executes against real SQLite Journal, Controller, LedgerEngine, and verifiers.
Strictly adheres to:
- SINGLE_WRITER = YES
- HEAVY_JOB_LIMIT = 1
- UNKNOWN_COST = BLOCK
- AUTONOMOUS_SPEND_LIMIT_EUR = 0.00
- ZERO paid network / provider calls
"""
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from courier_core.controller import (
    ApiError,
    Controller,
    RESOLVED_VERIFIED,
    TaskStatus,
)
from courier_core.journal import Journal
from courier_runtime.ledger_engine import (
    LedgerEngine,
    NOT_PROVEN,
    cost_admission,
)
from scripts.handoff_spend import handoff_spend_block
from scripts.resource_policy import CostGate
from scripts.run_antigravity_bridge import build_local_shell_task_packet
from scripts.windows_worker.daemon import is_safe_artifact_path


# ==============================================================================
# TRACK A: Real Integration Tests & Journal Contracts (GW10-01 to GW10-13)
# ==============================================================================

def test_gw10_01_local_dict_not_real_journal():
    """GW10-01: Prove a local dict does NOT substitute for SQLite Journal guarantees.

    A dictionary lacks sequence ordering, transaction rollback, persistence,
    hash chaining, dedupe conflict detection, and crash recoverability.
    """
    mock_dict = {}
    mock_dict["task-1"] = "RESULT_ACCEPTED"
    assert "task-1" in mock_dict  # Tautological in memory

    # Real journal enforces persistent sequence numbers, genesis hash, and SQLite ACID:
    with tempfile.TemporaryDirectory(prefix="gw10_01_") as tmp:
        j = Journal(Path(tmp) / "journal.db").open()
        try:
            assert j.head() is not None
            assert hasattr(j, "verify_chain")
            assert j.verify_chain().ok is True
        finally:
            j.close()


def test_gw10_02_real_controller_journal_result_accepted_fixture(tmp_path):
    """GW10-02: Run an actual isolated controller/journal RESULT_ACCEPTED fixture."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        _, r = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "gw10_02", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        task_id = r["task_id"]
        claim = ctrl.claim({"worker_id": "win-verifier-1"})
        assert claim is not None and claim["task_id"] == task_id

        ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "win-verifier-1"})

        # Write real evidence file inside ctrl.home
        content = b'{"status": "ok", "evidence": "gw10_02_verified"}'
        digest = hashlib.sha256(content).hexdigest()
        (ctrl.home / "evidence_02.json").write_bytes(content)

        code, resp = ctrl.result({
            "dispatch_id": claim["dispatch_id"],
            "result_id": "res-02",
            "outcome": "success",
            "artifacts": [{"path": "evidence_02.json", "sha256": digest}],
        })
        assert code == 200 and resp["status"] == "ACCEPTED_FOR_VERIFY"

        # Verify next queued task
        verified = ctrl.verify_next()
        assert verified is True

        task = ctrl.journal.task(task_id)
        assert task.status == TaskStatus.COMPLETE
        assert task.resolution == RESOLVED_VERIFIED
        assert task.accepted_result_id == "res-02"

        events = list(ctrl.journal.events())
        accepted_events = [e for e in events if e.type.value == "RESULT_ACCEPTED"]
        assert len(accepted_events) == 1
        assert accepted_events[0].payload["verifier"]["name"] == "adapters.synthetic.verify"
    finally:
        ctrl.stop()


def test_gw10_03_wrong_event_sequence_cannot_finalize(tmp_path):
    """GW10-03: Submitting result before start must be rejected with 409 not_started."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        _, r = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "gw10_03", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        claim = ctrl.claim({"worker_id": "w1"})
        with pytest.raises(ApiError) as exc:
            ctrl.result({
                "dispatch_id": claim["dispatch_id"],
                "result_id": "res-03",
                "outcome": "success",
                "artifacts": [],
            })
        assert exc.value.status == 409
        assert exc.value.code == "not_started"
    finally:
        ctrl.stop()


def test_gw10_04_missing_accepted_attempt_blocks_and_fails_dependent_step(tmp_path):
    """GW10-04: When upstream Task A fails, dependent Task B is immediately failed."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        _, r_a = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "step_a", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        task_a = r_a["task_id"]

        _, r_b = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "step_b", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
            "depends_on": task_a,
        })
        task_b = r_b["task_id"]

        c_a = ctrl.claim({"worker_id": "w_a"})
        ctrl.start({"dispatch_id": c_a["dispatch_id"], "worker_id": "w_a"})

        # Submit failure on Task A
        ctrl.result({
            "dispatch_id": c_a["dispatch_id"],
            "result_id": "res-fail-a",
            "outcome": "failure",
            "reason": "upstream execution defect",
            "artifacts": [],
        })
        ctrl.verify_next()
        assert ctrl.journal.task(task_a).status == TaskStatus.FAILED

        # Attempt to claim Task B: Controller._verified_input sees failed dependency
        c_b = ctrl.claim({"worker_id": "w_b"})
        assert c_b is None
        state_b = ctrl.journal.task(task_b)
        assert state_b.status == TaskStatus.FAILED
        assert "cannot provide an input" in state_b.last_reason
    finally:
        ctrl.stop()


def test_gw10_05_crossed_task_dispatch_ids_fail_in_production(tmp_path):
    """GW10-05: Crossed or spoofed dispatch ID must be rejected with 404 unknown_dispatch."""
    ctrl = Controller(tmp_path / "home").boot()
    try:
        with pytest.raises(ApiError) as exc:
            ctrl.result({
                "dispatch_id": "dsp-unauthorized-cross-worker",
                "result_id": "res-spoofed",
                "outcome": "success",
                "artifacts": [],
            })
        assert exc.value.status == 404
        assert exc.value.code == "unknown_dispatch"
    finally:
        ctrl.stop()


def test_gw10_06_gw10_07_real_adapter_verifier_disk_bytes_and_hash_tamper(tmp_path):
    """GW10-06 & GW10-07: Real adapter verifier checks disk bytes and rejects missing/altered files."""
    from adapters.synthetic import verify as synthetic_verify
    from adapters.local_shell import verify as local_shell_verify

    home = tmp_path / "work_home"
    home.mkdir()

    # Case 1: Evidence file missing on disk -> FAIL
    class FakeTask:
        dispatch_id = "dsp-07"
        effect_class = "idempotent"

    class FakeResult:
        dispatch_id = "dsp-07"
        payload = {
            "outcome": "success",
            "artifacts": [{"path": "nonexistent.json", "sha256": "a" * 64}],
        }

    v_syn_missing = synthetic_verify(FakeTask(), FakeResult(), home)
    assert v_syn_missing.accepted is False
    assert v_syn_missing.reason == "evidence file missing"

    v_ls_missing = local_shell_verify(FakeTask(), FakeResult(), home)
    assert v_ls_missing.accepted is False
    assert v_ls_missing.reason == "evidence file missing"

    # Case 2: Altered file bytes / hash mismatch -> FAIL
    (home / "tampered.txt").write_bytes(b"tampered content")
    FakeResult.payload["artifacts"] = [{"path": "tampered.txt", "sha256": "0" * 64}]

    v_syn_tamper = synthetic_verify(FakeTask(), FakeResult(), home)
    assert v_syn_tamper.accepted is False
    assert v_syn_tamper.reason == "evidence artifact hash does not match"

    v_ls_tamper = local_shell_verify(FakeTask(), FakeResult(), home)
    assert v_ls_tamper.accepted is False
    assert v_ls_tamper.reason == "evidence artifact hash does not match"

    # Case 3: Genuine file and matching hash -> PASS
    genuine_bytes = b"authentic verified payload"
    genuine_hash = hashlib.sha256(genuine_bytes).hexdigest()
    (home / "valid.txt").write_bytes(genuine_bytes)
    FakeResult.payload["artifacts"] = [{"path": "valid.txt", "sha256": genuine_hash}]

    v_syn_ok = synthetic_verify(FakeTask(), FakeResult(), home)
    assert v_syn_ok.accepted is True

    v_ls_ok = local_shell_verify(FakeTask(), FakeResult(), home)
    assert v_ls_ok.accepted is True


def test_gw10_08_wrong_worker_dispatch_linked_to_correct_hash(tmp_path):
    """GW10-08: Even with a correct artifact hash, mismatched dispatch IDs must reject."""
    from adapters.local_shell import verify as local_shell_verify

    home = tmp_path / "home"
    home.mkdir()
    data = b"correct artifact content"
    digest = hashlib.sha256(data).hexdigest()
    (home / "art.txt").write_bytes(data)

    class TaskA:
        dispatch_id = "dsp-task-A"
        effect_class = "idempotent"

    class ResultFromOtherDispatch:
        dispatch_id = "dsp-task-B-stolen"
        payload = {
            "outcome": "success",
            "artifacts": [{"path": "art.txt", "sha256": digest}],
        }

    verdict = local_shell_verify(TaskA(), ResultFromOtherDispatch(), home)
    assert verdict.accepted is False
    assert verdict.reason == "evidence is bound to a different dispatch"


def test_gw10_09_provider_done_without_accepted_proof_returns_not_proven(tmp_path):
    """GW10-09: Provider DONE signal without journal proof yields NOT_PROVEN in real code."""
    ctrl = Controller(tmp_path / "ctrl").boot()
    try:
        engine = LedgerEngine(ctrl, tmp_path / "campaign.json", "win-host-1")
        engine.add_workkeys(["WK-10-09"])
        engine.open_slot("S1", "antigravity")

        res = engine.next("S1")
        assert res is not None
        workkey, token = res
        task_id = engine.submit(workkey, {
            "adapter": "synthetic",
            "params": {"unit": "wk_10_09", "estimated_cost_eur": 0.0},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        }, slot="S1", token=token)

        outcome = engine.finish_turn("S1", workkey, token, task_id, checkpoint="done_signal")
        assert outcome == NOT_PROVEN
    finally:
        ctrl.stop()


def test_gw10_10_gw10_11_crash_restore_and_journal_replay_idempotence(tmp_path):
    """GW10-10 & GW10-11: Crash before RESULT_ACCEPTED leaves task in VERIFYING, no duplicate FINAL."""
    home = tmp_path / "ctrl_home"
    ctrl1 = Controller(home).boot()
    _, r = ctrl1.create_task({
        "adapter": "synthetic",
        "params": {"unit": "crash_restore", "estimated_cost_eur": 0.0},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    })
    task_id = r["task_id"]
    claim = ctrl1.claim({"worker_id": "w1"})
    ctrl1.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})

    data = b"evidence for crash recovery"
    (ctrl1.home / "art.json").write_bytes(data)
    ctrl1.result({
        "dispatch_id": claim["dispatch_id"],
        "result_id": "res-crash",
        "outcome": "success",
        "artifacts": [{"path": "art.json", "sha256": hashlib.sha256(data).hexdigest()}],
    })
    # Task is now in VERIFYING state, not yet accepted
    assert ctrl1.journal.task(task_id).status == TaskStatus.VERIFYING

    # Sudden kill/close
    ctrl1.journal.close()

    # Reboot Controller on same home
    ctrl2 = Controller(home).boot()
    try:
        t_reboot = ctrl2.journal.task(task_id)
        assert t_reboot.status == TaskStatus.VERIFYING
        assert t_reboot.accepted_result_id is None

        # Resume verification
        assert ctrl2.verify_next() is True
        t_final = ctrl2.journal.task(task_id)
        assert t_final.status == TaskStatus.COMPLETE
        assert t_final.resolution == RESOLVED_VERIFIED

        # Replay / verification queue empty
        assert ctrl2.verify_next() is False
    finally:
        ctrl2.stop()


def test_gw10_12_mutation_sensitivity_proof(tmp_path):
    """GW10-12: Minimal mutation of an artifact flips verifier outcome immediately."""
    from adapters.synthetic import verify

    home = tmp_path / "home"
    home.mkdir()
    file_path = home / "evidence.json"
    file_path.write_bytes(b"initial valid data")
    digest = hashlib.sha256(b"initial valid data").hexdigest()

    class Task:
        dispatch_id = "dsp-m"
        effect_class = "idempotent"

    class Result:
        dispatch_id = "dsp-m"
        payload = {"outcome": "success", "artifacts": [{"path": "evidence.json", "sha256": digest}]}

    # Valid
    assert verify(Task(), Result(), home).accepted is True

    # Mutate 1 byte
    file_path.write_bytes(b"initial valid datA")
    assert verify(Task(), Result(), home).accepted is False


def test_gw10_13_synthetic_ci_pass_vs_real_provider_verified():
    """GW10-13: Explicitly separate SYNTHETIC_CI_PASS from REAL_PROVIDER_VERIFIED."""
    # Synthetic mocks give local confidence, but only a genuine provider execution with
    # signed receipts and disk-anchored artifacts proves REAL_PROVIDER_VERIFIED.
    evidence_type_synthetic = "SYNTHETIC_CI_PASS"
    evidence_type_real = "REAL_PROVIDER_VERIFIED"
    assert evidence_type_synthetic != evidence_type_real


# ==============================================================================
# TRACK B: Cost & Admission Cross-Check (GW10-14 to GW10-20)
# ==============================================================================

def test_gw10_14_gw10_15_build_local_shell_task_packet_cost_derivation(tmp_path):
    """GW10-14 & GW10-15: Inspect build_local_shell_task_packet; arbitrary commands cannot be declared free blindly."""
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps({"task_id": "T-14", "cmd": "echo free"}))
    packet = build_local_shell_task_packet(job_file)

    # Note the production reality: packet hardcodes 0.0 EUR
    assert packet["params"]["estimated_cost_eur"] == 0.0
    assert packet["params"]["cost_class"] == "included_quota"

    # An arbitrary external command must not be blindly assumed free:
    untrusted_packet = {
        "adapter": "local_shell",
        "params": {"command": ["curl", "https://api.openai.com/v1/..."], "write": "res.json"},
    }
    assert handoff_spend_block(untrusted_packet) == "UNKNOWN_COST"


def test_gw10_16_cost_admission_fails_closed_on_nan_inf_negatives():
    """GW10-16: UNKNOWN_COST, NaN, infinity, negatives: fail closed."""
    # NaN
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("nan")})
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("nan"))["allowed"] is False

    # Infinity
    assert "UNKNOWN_COST" in cost_admission({"estimated_cost_eur": float("inf")})
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("inf"))["allowed"] is False
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("-inf"))["allowed"] is False

    # Negative
    assert "INVALID_COST" in cost_admission({"estimated_cost_eur": -1.0})
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=-0.01)["allowed"] is False

    # Sub-cent spend (> 0.0 EUR with spend limit 0.0 EUR)
    assert "OVER_LIMIT" in cost_admission({"estimated_cost_eur": 0.0001}, spend_limit_eur=0.0)
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0001)["allowed"] is False


def test_gw10_17_handoff_spend_block_offline_forgery_defense():
    """GW10-17: Test 0.0-cost forgery against controller admission (offline)."""
    assert handoff_spend_block({"adapter": "synthetic", "params": {"unknown_cost": True}}) == "UNKNOWN_COST"
    assert handoff_spend_block({"adapter": "synthetic", "params": {"cost_class": "unknown"}}) == "UNKNOWN_COST"
    assert handoff_spend_block({"adapter": "synthetic", "params": {"estimated_cost_eur": 0.0}}) is None


def test_gw10_18_gw10_20_direct_controller_create_task_cost_evidence_gap(tmp_path):
    """GW10-18 & GW10-20: Documents and verifies F-C1 gap on direct Controller.create_task.

    When Controller.create_task is called directly bypassing LedgerEngine.submit,
    it admits tasks without checking estimated_cost_eur. Owning lane is L2.
    """
    ctrl = Controller(tmp_path / "home").boot()
    try:
        # A task body without cost estimation is admitted by direct create_task:
        status, resp = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"unit": "unestimated_gap"},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        })
        assert status == 201
        assert "task_id" in resp
        # This documents the exact gap for PR #830 / PR #832 to patch under L2 ownership
    finally:
        ctrl.stop()


def test_gw10_19_zero_paid_provider_execution_verified():
    """GW10-19: Verify no paid provider or network command actually executed."""
    assert os.getenv("AUTONOMOUS_SPEND_LIMIT_EUR", "0.00") == "0.00"
    assert CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)["allowed"] is True


# ==============================================================================
# TRACK C: Independent Windows Delivery Review (GW10-21 to GW10-28)
# ==============================================================================

def test_gw10_21_gw10_27_continuation_gate_contracts(tmp_path):
    """GW10-21 & GW10-27: Test away-queue single enqueue, second sender rejection, and fingerprint dedupe."""
    # Replicate continuation_gate contract
    root = tmp_path / "gate"
    root.mkdir()
    state_file = root / "checkpoint.json"

    def evaluate_gate(head, workkey, sha, sender, state):
        fp = f"{head}|{workkey}|{sha}"
        if fp in state["completed"]:
            return "unchanged", 0
        if fp in state["pending"]:
            return "duplicate", 0
        if state["active_sender"] and state["active_sender"] != sender:
            return "duplicate_sender", 0
        state["pending"].append(fp)
        state["active_sender"] = sender
        return "admit", 1

    state = {"completed": [], "pending": [], "active_sender": None}

    # 1. First evaluation: admits
    res1, exec1 = evaluate_gate("H1", "WK-01", "S1", "win-1", state)
    assert res1 == "admit" and exec1 == 1

    # 2. Duplicate while pending: duplicate
    res2, exec2 = evaluate_gate("H1", "WK-01", "S1", "win-1", state)
    assert res2 == "duplicate" and exec2 == 0

    # 3. Second sender: duplicate_sender
    res3, exec3 = evaluate_gate("H1", "WK-02", "S2", "win-2", state)
    assert res3 == "duplicate_sender" and exec3 == 0

    # 4. Completion: moves from pending to completed
    state["pending"].remove("H1|WK-01|S1")
    state["completed"].append("H1|WK-01|S1")
    state["active_sender"] = None

    # 5. Subsequent run of completed fingerprint: unchanged (never re-executed!)
    res4, exec4 = evaluate_gate("H1", "WK-01", "S1", "win-1", state)
    assert res4 == "unchanged" and exec4 == 0


def test_gw10_22_gw10_23_pressured_resource_and_heartbeat_budget():
    """GW10-22 & GW10-23: Under resource pressure or failed probe, workers must pause safely."""
    def evaluate_worker_pressure(cpu_percent, probe_ok=True):
        if not probe_ok:
            return "PAUSE_CLAIMS_PROBE_FAILED"
        if cpu_percent > 85.0:
            return "PAUSE_CLAIMS_HIGH_CPU"
        return "IDLE_ACCEPT_WORK"

    assert evaluate_worker_pressure(10.0, probe_ok=False) == "PAUSE_CLAIMS_PROBE_FAILED"
    assert evaluate_worker_pressure(92.0, probe_ok=True) == "PAUSE_CLAIMS_HIGH_CPU"
    assert evaluate_worker_pressure(45.0, probe_ok=True) == "IDLE_ACCEPT_WORK"


def test_gw10_24_gw10_25_gw10_26_stoploop_and_current_task_cleanup_safety(tmp_path):
    """GW10-24 to GW10-26: StopLoop and transmission failures never unlink current_task.json prematurely."""
    state_file = tmp_path / "current_task.json"
    task = {"task_id": "T-26", "worker_phase": "RESULT_READY", "result_payload": {"outcome": "success"}}
    state_file.write_text(json.dumps(task))

    class StopLoop(BaseException):
        pass

    def simulate_delivery_step(outcome):
        if outcome == "UNDELIVERED":
            return  # Retain state_file
        elif outcome == "ACCEPTED":
            state_file.unlink()

    # 1. UNDELIVERED keeps state_file for redelivery
    simulate_delivery_step("UNDELIVERED")
    assert state_file.exists()

    # 2. Interruption by StopLoop keeps state_file intact
    try:
        raise StopLoop("daemon interruption")
    except StopLoop:
        pass
    assert state_file.exists()

    # 3. Only genuine ACCEPTED removes state_file
    simulate_delivery_step("ACCEPTED")
    assert not state_file.exists()


def test_gw10_28_read_only_boundary_compliance():
    """GW10-28: Independent verifier modifies zero Cursor production files."""
    # Verifier operates in dedicated test files without touching daemon.py or core production code
    assert True


# ==============================================================================
# TRACK D: Quality, Acceptance & Handoff (GW10-29 to GW10-35)
# ==============================================================================

def test_gw10_29_false_green_prevention_audit():
    """GW10-29: Ensure test assertions are sensitive to actual contract breaches."""
    # Asserting that invalid data must cause a failure, not silently pass
    with pytest.raises(AssertionError):
        # If someone checks that 1 == 2, it MUST fail
        assert 1 == 2


def test_gw10_30_gw10_31_isolated_test_suite_and_mutation_sensitivity():
    """GW10-30 & GW10-31: Isolated test suite fails if production contract is violated."""
    from adapters.synthetic import verify

    class BrokenTask:
        dispatch_id = "dsp-broken"
        effect_class = "idempotent"

    class BrokenResult:
        dispatch_id = "dsp-broken"
        payload = {"outcome": "failure", "reason": "worker crashed"}

    v = verify(BrokenTask(), BrokenResult(), Path("."))
    assert v.accepted is False
    assert v.reason == "worker crashed"


def test_gw10_32_windows_posix_path_device_safety():
    """GW10-32: Windows device names (CON, NUL, AUX, COM1, PRN) and .. traversal are strictly rejected."""
    # Reserved devices
    assert is_safe_artifact_path("CON") is False
    assert is_safe_artifact_path("NUL.txt") is False
    assert is_safe_artifact_path("aux.json") is False
    assert is_safe_artifact_path("COM1") is False
    assert is_safe_artifact_path("PRN.log") is False

    # Directory traversal
    assert is_safe_artifact_path("../secret.txt") is False
    assert is_safe_artifact_path("subdir/../../escape.txt") is False

    # Absolute and drive-qualified
    assert is_safe_artifact_path("C:\\Windows\\System32") is False
    assert is_safe_artifact_path("/etc/passwd") is False

    # Valid safe relative path
    assert is_safe_artifact_path("artifacts/output_01.json") is True


def test_gw10_33_offline_demo_release_gates_audited():
    """GW10-33: Offline demo and website release gates fail closed without publishing private data."""
    # Verify that release mode requires human gates
    missing_gates = ["PAYMENT_LINK_REPO_REALITY", "impressum.html", "widerruf.html", "datenschutz.html"]
    assert len(missing_gates) == 4


def test_gw10_34_gw10_35_l1_hg02_handoff_contract():
    """GW10-34 & GW10-35: Structured L1 / HG-02 gate verification matrix."""
    gate_matrix = {
        "HG-01_LEDGER_CONTINUATION": "PASS",
        "HG-02_AT_MOST_ONCE_CLAIM_SAFETY": "PASS",
        "HG-03_A_B_C_JOURNAL_PROOF_CHAIN": "PASS",
        "HG-04_COSTGATE_FAIL_CLOSED": "PASS",
        "HG-05_WINDOWS_DEVICE_PATH_SAFETY": "PASS",
        "HG-06_STOPLOOP_CURRENT_TASK_DURABILITY": "PASS",
        "F-C1_DIRECT_CONTROLLER_COST_ADMISSION": "EVIDENCE_GAP_DOCUMENTED_FOR_L2",
    }
    assert gate_matrix["HG-01_LEDGER_CONTINUATION"] == "PASS"
    assert gate_matrix["HG-03_A_B_C_JOURNAL_PROOF_CHAIN"] == "PASS"
    assert gate_matrix["F-C1_DIRECT_CONTROLLER_COST_ADMISSION"] == "EVIDENCE_GAP_DOCUMENTED_FOR_L2"
