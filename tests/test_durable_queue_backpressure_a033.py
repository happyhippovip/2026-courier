"""Tests for Durable Queue Backpressure and Saturation Control (ANTIGRAVITY 033).

Verifies fail-closed queue admission, backpressure, and TRUE_IDLE invariants:
Scenario A: Duplicate workkey submitted multiple times -> Deduplicated, exactly 1 admitted.
Scenario B: High-volume workkeys submitted (65 tasks) -> Backpressure applies bounded limit, remainder buffered.
Scenario C: Host heavy job capacity exhausted -> Admission fails closed (CAPACITY_EXHAUSTED).
Scenario D: Already completed workkey re-submitted -> Rejected (rejected_completed), zero re-execution.
Scenario E: Queue empty of pending tasks but unharvested results exist -> Transitions to HARVEST_REQUIRED.
Scenario F: Queue truly empty and all results harvested -> Reaches TRUE_IDLE without polling overhead.
Resume Scenario: Releasing completed tasks admits previously buffered tasks without re-executing.
"""

import pytest

from courier_runtime.admission_gate import (
    ProgressGate,
    QueueBackpressureGate,
    QueueBatchResult,
)


def test_scenario_a_duplicate_workkey_deduplication():
    """Scenario A: One workkey offered multiple times in the same queue batch.
    
    Must admit exactly once; all subsequent identical workkeys rejected as duplicates.
    Zero duplicate executions.
    """
    gate = QueueBackpressureGate(max_batch_size=10, heavy_job_limit=1)
    incoming = ["TASK-ALPHA", "TASK-ALPHA", "TASK-ALPHA", "TASK-ALPHA"]

    result = gate.process_queue_intake(incoming)

    assert result.admitted == ["TASK-ALPHA"]
    assert result.rejected_duplicates == ["TASK-ALPHA", "TASK-ALPHA", "TASK-ALPHA"]
    assert result.status == "ADMITTED"
    assert len(result.admitted) == 1


def test_scenario_b_many_workkeys_bounded_backpressure():
    """Scenario B: High-volume tasks submitted (e.g. 65 distinct tasks).
    
    Must apply backpressure, admitting only up to bounded batch size (5),
    buffering the remaining 60 tasks without dropped state or host memory exhaustion.
    """
    gate = QueueBackpressureGate(max_batch_size=5, heavy_job_limit=1)
    incoming = [f"TASK-MASSIVE-{i:03d}" for i in range(65)]

    result = gate.process_queue_intake(incoming)

    assert len(result.admitted) == 5
    assert len(result.buffered) == 60
    assert result.status == "SATURATED_BACKPRESSURE"
    assert "buffered under backpressure" in result.reason


def test_scenario_c_host_capacity_denial():
    """Scenario C: Host capacity does not allow another heavy job.
    
    When current_heavy_jobs >= heavy_job_limit, admission fails closed.
    Zero new heavy jobs started.
    """
    gate = QueueBackpressureGate(max_batch_size=5, heavy_job_limit=1)
    incoming = ["HEAVY-TASK-01", "HEAVY-TASK-02"]

    result = gate.process_queue_intake(
        incoming, current_heavy_jobs=1, is_heavy_batch=True
    )

    assert result.status == "CAPACITY_EXHAUSTED"
    assert len(result.admitted) == 0
    assert result.capacity_denied == ["HEAVY-TASK-01", "HEAVY-TASK-02"]


def test_scenario_d_already_completed_workkey_rejected():
    """Scenario D: Already completed workkey appears in the queue again.
    
    Progress gate history records task as COMPLETED; re-admission rejected.
    """
    progress = ProgressGate()
    progress.record_outcome(
        workkey="TASK-DONE-ALREADY",
        baseline_checkpoint="cp-001",
        input_fingerprint="fp-001",
        evidence_fingerprint="ev-001",
        status="COMPLETED",
    )
    gate = QueueBackpressureGate(max_batch_size=5, heavy_job_limit=1, progress_gate=progress)

    incoming = ["TASK-DONE-ALREADY", "TASK-NEW-01"]
    result = gate.process_queue_intake(incoming)

    assert result.admitted == ["TASK-NEW-01"]
    assert result.rejected_completed == ["TASK-DONE-ALREADY"]
    assert "TASK-DONE-ALREADY" not in result.admitted


def test_scenario_e_unharvested_results_require_harvest():
    """Scenario E: Queue is empty of tasks, but unharvested results are pending.
    
    Must NOT transition to TRUE_IDLE; indicates HARVEST_REQUIRED.
    """
    gate = QueueBackpressureGate(max_batch_size=5, heavy_job_limit=1)

    result = gate.process_queue_intake(
        candidate_workkeys=[], unharvested_results_count=3
    )

    assert result.status == "HARVEST_REQUIRED"
    assert len(result.admitted) == 0
    assert "pending harvest before idle" in result.reason


def test_scenario_f_empty_queue_all_results_harvested_true_idle():
    """Scenario F: Queue is empty and all results are harvested.
    
    Reaches clean TRUE_IDLE; prevents continuous model polling loops.
    """
    gate = QueueBackpressureGate(max_batch_size=5, heavy_job_limit=1)

    result = gate.process_queue_intake(
        candidate_workkeys=[], unharvested_results_count=0
    )

    assert result.status == "TRUE_IDLE"
    assert len(result.admitted) == 0
    assert "zero model polling required" in result.reason


def test_resume_after_pressure_and_capacity_recovery():
    """Test resume: Releasing completed tasks allows buffered tasks to be admitted."""
    gate = QueueBackpressureGate(max_batch_size=2, heavy_job_limit=1)
    incoming = ["TASK-1", "TASK-2", "TASK-3", "TASK-4"]

    # Step 1: First batch admits 2, buffers 2 under backpressure
    batch1 = gate.process_queue_intake(incoming)
    assert batch1.admitted == ["TASK-1", "TASK-2"]
    assert batch1.buffered == ["TASK-3", "TASK-4"]

    # Step 2: Task 1 finishes and releases capacity
    gate.release_task("TASK-1")

    # Step 3: Next cycle with remaining buffered tasks admits TASK-3
    batch2 = gate.process_queue_intake(batch1.buffered)
    assert batch2.admitted == ["TASK-3"]
    assert batch2.buffered == ["TASK-4"]

    # Step 4: Task 2 and Task 3 release capacity
    gate.release_task("TASK-2")
    gate.release_task("TASK-3")

    # Step 5: Final task TASK-4 admitted cleanly
    batch3 = gate.process_queue_intake(batch2.buffered)
    assert batch3.admitted == ["TASK-4"]
    assert batch3.buffered == []
    assert batch3.status == "ADMITTED"
