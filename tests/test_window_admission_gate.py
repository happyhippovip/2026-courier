import pytest
from courier_runtime.admission_gate import (
    WindowAdmissionGate,
    WindowTarget,
    TerminalGeometry,
    AdmissionDecision,
    ProgressGate,
    ExecutionAudit,
    MIN_COLS,
    MIN_ROWS,
)


def _make_target(window_id="win-term-01", is_busy=False, cols=80, rows=24, custody="SAFE_TO_REUSE"):
    return WindowTarget(
        window_id=window_id,
        title=f"Terminal — {cols}×{rows}",
        host="darwin_x86_64",
        geometry=TerminalGeometry(cols=cols, rows=rows),
        custody_state=custody,
        is_busy=is_busy,
        is_accessible=True,
    )


def test_admission_success_on_idle_80x24_window():
    gate = WindowAdmissionGate(heavy_job_limit=1)
    target = _make_target()
    decision = gate.evaluate(
        target=target,
        workkey="WF-TASK-PILOT-01",
        session_id="session-mac-01",
        provider_capacity_ok=True,
        current_heavy_jobs=0,
    )
    assert decision.decision == "ADMIT"
    assert decision.receipt_id is not None
    assert decision.receipt_id.startswith("adm-")
    assert decision.dedupe_key is not None


def test_terminal_too_small_rejection():
    """Reproduces the user observed 'Terminal too small' failure on squished windows."""
    gate = WindowAdmissionGate()
    target = _make_target(cols=20, rows=16, custody="IDLE")
    decision = gate.evaluate(
        target=target,
        workkey="WF-TASK-PILOT-02",
        session_id="session-mac-01",
    )
    assert decision.decision == "REJECT"
    assert any("TERMINAL_TOO_SMALL" in r for r in decision.reasons)
    assert any("20x16 < required 80x24" in r for r in decision.reasons)


def test_busy_window_rejected():
    gate = WindowAdmissionGate()
    target = _make_target(is_busy=True, custody="IDLE")
    decision = gate.evaluate(
        target=target,
        workkey="WF-TASK-PILOT-03",
        session_id="session-mac-01",
    )
    assert decision.decision == "REJECT"
    assert any("ACTIVE_WORK_IN_PROGRESS" in r for r in decision.reasons)


def test_unproven_custody_rejected():
    gate = WindowAdmissionGate()
    target = _make_target(custody="UNKNOWN_CUSTODY")
    decision = gate.evaluate(
        target=target,
        workkey="WF-TASK-PILOT-04",
        session_id="session-mac-01",
    )
    assert decision.decision == "REJECT"
    assert any("UNPROVEN_CUSTODY" in r for r in decision.reasons)


def test_workkey_collision_rejected():
    gate = WindowAdmissionGate()
    target1 = _make_target(window_id="win-01", custody="IDLE")
    target2 = _make_target(window_id="win-02", custody="IDLE")

    d1 = gate.evaluate(target1, "WF-SHARED-01", "session-A")
    assert d1.decision == "ADMIT"

    d2 = gate.evaluate(target2, "WF-SHARED-01", "session-B")
    assert d2.decision == "REJECT"
    assert any("WORKKEY_COLLISION" in r for r in d2.reasons)


def test_duplicate_submission_prevented():
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-01", custody="IDLE")

    d1 = gate.evaluate(target, "WF-ONCE-01", "session-A")
    assert d1.decision == "ADMIT"

    d2 = gate.evaluate(target, "WF-ONCE-01", "session-A")
    assert d2.decision == "REJECT"
    assert any("DUPLICATE_SUBMISSION" in r for r in d2.reasons)


def test_release_and_reuse():
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-01", custody="IDLE")

    d1 = gate.evaluate(target, "WF-TASK-1", "session-A")
    assert d1.decision == "ADMIT"

    gate.release("win-01", "WF-TASK-1")

    d2 = gate.evaluate(target, "WF-TASK-2", "session-A")
    assert d2.decision == "ADMIT"


# ============================================================================
# Acceptance Scenarios A through F (Progress Gate Verification)
# ============================================================================

def test_acceptance_a_completed_workkey_selected_again_rejected():
    """TEST A: The same completed workkey is selected again.
    Expected: no duplicate execution or side effect (ALREADY_COMPLETED).
    """
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-A")

    # First run admits and completes
    d1 = gate.evaluate(
        target, "WF-A", "session-1",
        input_fingerprint="fp-initial-code",
        baseline_checkpoint="2cc9c89e",
    )
    assert d1.decision == "ADMIT"
    gate.record_progress(
        workkey="WF-A",
        baseline_checkpoint="2cc9c89e",
        input_fingerprint="fp-initial-code",
        evidence_fingerprint="evidence-v1",
        status="COMPLETED",
    )
    gate.release("win-A", "WF-A")

    # Second selection with same evidence is rejected
    d2 = gate.evaluate(
        target, "WF-A", "session-1",
        input_fingerprint="fp-initial-code",
        baseline_checkpoint="2cc9c89e",
        new_evidence_fingerprint="evidence-v1",
    )
    assert d2.decision == "REJECT"
    assert any("ALREADY_COMPLETED" in r for r in d2.reasons)


def test_acceptance_b_same_analysis_unchanged_fingerprint_loop_prevented():
    """TEST B: The same analysis runs against unchanged source, fingerprint and evidence.
    Expected: no new productive task is admitted merely because time passed (LOOP_PREVENTED).
    """
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-B")

    d1 = gate.evaluate(
        target, "WF-ANALYSIS-01", "session-1",
        input_fingerprint="fp-unchanged-ast",
        baseline_checkpoint="2cc9c89e",
    )
    assert d1.decision == "ADMIT"

    # Worker marks blocked / no-progress
    gate.record_progress(
        workkey="WF-ANALYSIS-01",
        baseline_checkpoint="2cc9c89e",
        input_fingerprint="fp-unchanged-ast",
        evidence_fingerprint=None,
        status="BLOCKED",
    )
    gate.release("win-B", "WF-ANALYSIS-01")

    # Time passes; caller attempts to run exact same analysis on unchanged code/fingerprint
    d2 = gate.evaluate(
        target, "WF-ANALYSIS-01", "session-1",
        input_fingerprint="fp-unchanged-ast",
        baseline_checkpoint="2cc9c89e",
        new_evidence_fingerprint=None,
    )
    assert d2.decision == "REJECT"
    assert any("LOOP_PREVENTED" in r for r in d2.reasons)


def test_acceptance_c_dependency_changes_produces_new_evidence_admitted():
    """TEST C: A dependency changes and produces valid new evidence.
    Expected: the blocked work becomes eligible for controlled continuation.
    """
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-C")

    # Initial state was blocked
    gate.record_progress(
        workkey="WF-WAIT-DEP",
        baseline_checkpoint="2cc9c89e",
        input_fingerprint="fp-dep-blocked",
        evidence_fingerprint="dep-hash-v1",
        status="BLOCKED",
    )

    # Dependency updates -> produces new evidence hash 'dep-hash-v2'
    decision = gate.evaluate(
        target, "WF-WAIT-DEP", "session-1",
        input_fingerprint="fp-dep-blocked",
        baseline_checkpoint="2cc9c89e",
        new_evidence_fingerprint="dep-hash-v2",
    )
    assert decision.decision == "ADMIT"
    assert decision.receipt_id is not None


def test_acceptance_d_uncertain_outcome_fails_closed():
    """TEST D: A non-idempotent outcome is uncertain.
    Expected: fail closed; no blind retry.
    """
    gate = WindowAdmissionGate()
    target = _make_target(window_id="win-D")

    decision = gate.evaluate(
        target, "WF-PAYMENT-MIGRATION", "session-1",
        input_fingerprint="fp-migration",
        baseline_checkpoint="2cc9c89e",
        is_uncertain=True,
    )
    assert decision.decision == "REJECT"
    assert any("UNCERTAIN_OUTCOME_FAIL_CLOSED" in r for r in decision.reasons)


def test_acceptance_e_host_pressure_and_provider_unavailable():
    """TEST E: A provider is unavailable or the host is under pressure.
    Expected: checkpoint preserved, no retry storm or additional heavy process.
    """
    gate = WindowAdmissionGate(heavy_job_limit=1)
    target = _make_target(window_id="win-E")

    # Host pressure reject
    d1 = gate.evaluate(
        target, "WF-HEAVY", "session-1",
        current_heavy_jobs=1,
    )
    assert d1.decision == "REJECT"
    assert any("HOST_PRESSURE" in r for r in d1.reasons)

    # Provider unavailable reject
    d2 = gate.evaluate(
        target, "WF-NORMAL", "session-1",
        provider_capacity_ok=False,
    )
    assert d2.decision == "REJECT"
    assert any("PROVIDER_CAPACITY_EXHAUSTED" in r for r in d2.reasons)


def test_acceptance_f_real_verified_result_progresses_ledger():
    """TEST F: A real verified result arrives.
    Expected: canonical ledger progresses and the next eligible task may proceed exactly once.
    """
    gate = WindowAdmissionGate()
    target1 = _make_target(window_id="win-F1")
    target2 = _make_target(window_id="win-F2")

    # Task 1 admits and completes with verified receipt
    d1 = gate.evaluate(
        target1, "WF-STEP-1", "session-1",
        input_fingerprint="fp-task1",
        baseline_checkpoint="2cc9c89e",
    )
    assert d1.decision == "ADMIT"

    # Verified progress recorded
    gate.record_progress(
        workkey="WF-STEP-1",
        baseline_checkpoint="2cc9c89e",
        input_fingerprint="fp-task1",
        evidence_fingerprint="sha-verified-test-passed",
        status="COMPLETED",
    )
    gate.release("win-F1", "WF-STEP-1")

    # Next eligible task (WF-STEP-2) advances cleanly
    d2 = gate.evaluate(
        target2, "WF-STEP-2", "session-1",
        input_fingerprint="fp-task2",
        baseline_checkpoint="sha-verified-test-passed",
    )
    assert d2.decision == "ADMIT"


def test_execution_audit_started_is_not_completed():
    audit = ExecutionAudit(
        command="python3 .github/ci/check_golden_skips.py",
        execution_handle="task-10989",
        started=True,
        completed=False,
        exit_code=None,
        output_captured=False,
    )
    ok, reason = audit.validate_verdict(claimed_pass=True)
    assert ok is False
    assert "COMMAND_STARTED_IS_NOT_COMPLETED" in reason
    assert audit.is_passed is False


def test_execution_audit_completed_with_failure_is_not_passed():
    audit = ExecutionAudit(
        command="python3 .github/ci/check_golden_skips.py",
        execution_handle="task-10989",
        started=True,
        completed=True,
        exit_code=1,
        output_captured=True,
    )
    ok, reason = audit.validate_verdict(claimed_pass=True)
    assert ok is False
    assert "COMMAND_COMPLETED_IS_NOT_PASSED" in reason
    assert audit.is_passed is False


def test_execution_audit_missing_captured_output_fails_validation():
    audit = ExecutionAudit(
        command="python3 -m unittest",
        execution_handle="task-10990",
        started=True,
        completed=True,
        exit_code=0,
        output_captured=False,
    )
    ok, reason = audit.validate_verdict(claimed_pass=True)
    assert ok is False
    assert "MISSING_EVIDENCE" in reason
    assert audit.is_passed is False


def test_execution_audit_genuine_verified_pass():
    audit = ExecutionAudit(
        command="pytest tests/test_window_admission_gate.py",
        execution_handle="task-10991",
        started=True,
        completed=True,
        exit_code=0,
        output_captured=True,
    )
    ok, reason = audit.validate_verdict(claimed_pass=True)
    assert ok is True
    assert reason == "VERIFIED"
    assert audit.is_passed is True

