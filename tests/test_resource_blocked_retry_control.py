"""Test Suite for A012: Resource-Blocked Retry Control.

Verifies:
1. Ralph-V154 incident prevention: admission rejection transitions task to BLOCKED.
2. Durable persistence of blocked reason, retry count, wake-up condition, and MODEL_CALLS=0.
3. Queue processor suppresses fast retry loops across multiple sweeps.
4. Clean reload in fresh process recovers identical blocked attributes.
5. Wake-up condition enables clean resumption once resources are healthy.
"""

import json
import os
import sys
from unittest import mock
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from scripts import queue_processor, intake_dispatcher
from scripts.intake_dispatcher import (
    ADMISSION_BLOCKED,
    ADMISSION_ADMITTED,
    fingerprint_task_id,
    load_central_state,
    unblock_task,
)


def _sample_heavy_intake(ref="ralph-v154-job"):
    return {
        "customer_reference": ref,
        "target_owner": "org",
        "target_repo": "courier-heavy",
        "target_sha": "d05bb26db",
        "job_weight": "HEAVY",
    }


def test_resource_blocked_admission_records_durable_state_and_zero_model_calls(tmp_path, monkeypatch):
    """A012 Part 1: Artificial admission rejection records BLOCKED, durable reason, and MODEL_CALLS=0."""
    monkeypatch.chdir(tmp_path)
    intake_data = _sample_heavy_intake()
    task_id = fingerprint_task_id(intake_data)
    intake_file = tmp_path / "heavy_task.json"
    intake_file.write_text(json.dumps(intake_data))

    model_calls = []

    def fake_subprocess_run(*args, **kwargs):
        model_calls.append(args)
        return mock.Mock(returncode=0)

    # Artificial admission evaluator simulating host memory/swap pressure
    def artificial_admission_evaluator(intake):
        return {
            "decision": "BLOCKED",
            "reason": "HOST_PRESSURE: memory_pressure 89.2% > 80.0%, swap elevated",
            "wakeup_condition": "RESOURCE_HEALTHY",
            "max_retries": 4,
        }

    with mock.patch("scripts.intake_dispatcher.subprocess.run", side_effect=fake_subprocess_run):
        decision_task_id = intake_dispatcher.dispatch_intake(
            str(intake_file), admission_checker=artificial_admission_evaluator
        )

    # 1. Dispatcher decision is BLOCKED
    assert decision_task_id == task_id
    assert len(model_calls) == 0, f"Expected 0 model calls, got {len(model_calls)}"

    # 2. Durable state verification
    state = load_central_state("central_state.json")
    task_rec = state["tasks"][task_id]

    assert task_rec["task_id"] == task_id
    assert task_rec["admission"] == ADMISSION_BLOCKED
    assert task_rec["state"] == "BLOCKED"
    assert "HOST_PRESSURE" in task_rec["blocked_reason"]
    assert task_rec["retry_count"] == 1
    assert task_rec["max_retries"] == 4
    assert task_rec["wakeup_condition"] == "RESOURCE_HEALTHY"
    assert task_rec["model_calls"] == 0

    # 3. Reload in fresh independent reading process (isolated sub-check)
    fresh_state = json.loads((tmp_path / "central_state.json").read_text())
    assert fresh_state["tasks"][task_id]["admission"] == "BLOCKED"
    assert fresh_state["tasks"][task_id]["retry_count"] == 1


def test_no_fast_retry_loop_on_resource_blockage(tmp_path, monkeypatch):
    """A012 Part 2: Prevents the Ralph-V154 4-rejection tight retry loop across queue sweeps."""
    monkeypatch.chdir(tmp_path)
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    intake_data = _sample_heavy_intake("heavy-queue-job-1")
    task_id = fingerprint_task_id(intake_data)
    task_file = pending_dir / "job_01.json"
    task_file.write_text(json.dumps(intake_data))

    evaluator_invocations = []
    subprocess_invocations = []

    def mock_evaluator(intake):
        evaluator_invocations.append(intake)
        return {
            "decision": "BLOCKED",
            "reason": "RESOURCE_PRESSURE: swap 19.1GB / 19.5GB",
            "wakeup_condition": "RESOURCE_HEALTHY",
        }

    with mock.patch("scripts.intake_dispatcher.subprocess.run", side_effect=lambda *a, **k: subprocess_invocations.append(a)):
        # SWEEP 1: First attempt evaluates admission, detects resource blockage, sets BLOCKED state
        queue_processor.process_queue(admission_checker=mock_evaluator)
        assert len(evaluator_invocations) == 1
        assert len(subprocess_invocations) == 0

        # State is recorded as BLOCKED
        state_after_1 = load_central_state("central_state.json")
        assert state_after_1["tasks"][task_id]["admission"] == ADMISSION_BLOCKED
        assert state_after_1["tasks"][task_id]["retry_count"] == 1

        # File remains parked in pending (not erroneously moved to processed)
        assert task_file.exists()
        assert not (processed_dir / "job_01.json").exists()

        # SWEEPS 2, 3, 4: Subsequent sweeps simulate repeated periodic cron/wake calls within minutes
        for sweep in range(2, 5):
            queue_processor.process_queue(admission_checker=mock_evaluator)

        # PROOF: Evaluator was NOT called again during sweeps 2, 3, 4!
        # Fast retry loop is completely eliminated.
        assert len(evaluator_invocations) == 1, (
            f"Expected only 1 admission check across 4 sweeps, got {len(evaluator_invocations)}"
        )
        assert len(subprocess_invocations) == 0, (
            f"Expected zero external/model executions, got {len(subprocess_invocations)}"
        )

        # Retry count remains strictly preserved at 1 (no thrashing)
        state_after_4 = load_central_state("central_state.json")
        assert state_after_4["tasks"][task_id]["retry_count"] == 1
        assert state_after_4["tasks"][task_id]["admission"] == ADMISSION_BLOCKED


def test_resource_pause_file_triggers_blocked_decision(tmp_path, monkeypatch):
    """A012 Part 3: Standard RESOURCE_PAUSE file triggers durable BLOCKED state."""
    monkeypatch.chdir(tmp_path)
    pause_file = tmp_path / "RESOURCE_PAUSE"
    pause_file.write_text("RESOURCE_PAUSE set: load 114/16 cores, swap 95% full")

    intake_data = _sample_heavy_intake("pause-test-job")
    task_id = fingerprint_task_id(intake_data)
    intake_file = tmp_path / "job_paused.json"
    intake_file.write_text(json.dumps(intake_data))

    dispatched = []
    with mock.patch("scripts.intake_dispatcher.subprocess.run", side_effect=lambda *a, **k: dispatched.append(a)):
        res_task_id = intake_dispatcher.dispatch_intake(str(intake_file))

    assert res_task_id == task_id
    assert len(dispatched) == 0

    state = load_central_state("central_state.json")
    task_rec = state["tasks"][task_id]
    assert task_rec["admission"] == ADMISSION_BLOCKED
    assert "RESOURCE_PAUSE" in task_rec["blocked_reason"]
    assert task_rec["model_calls"] == 0


def test_wakeup_condition_enables_resumption(tmp_path, monkeypatch):
    """A012 Part 4: Satisfying wake-up condition unblocks task and enables admission."""
    monkeypatch.chdir(tmp_path)
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    intake_data = _sample_heavy_intake("resumption-job")
    task_id = fingerprint_task_id(intake_data)
    task_file = pending_dir / "job_resumed.json"
    task_file.write_text(json.dumps(intake_data))

    # Initial state is BLOCKED
    state = {
        "tasks": {
            task_id: {
                "task_id": task_id,
                "admission": ADMISSION_BLOCKED,
                "state": "BLOCKED",
                "blocked_reason": "RESOURCE_PRESSURE",
                "retry_count": 1,
                "wakeup_condition": "RESOURCE_HEALTHY",
                "model_calls": 0,
            }
        }
    }
    intake_dispatcher.save_central_state("central_state.json", state)

    # Sweep while blocked does not process
    queue_processor.process_queue()
    assert task_file.exists()
    assert not (processed_dir / "job_resumed.json").exists()

    # Operator or health monitor clears block
    unblock_ok = unblock_task(task_id, reason="RESOURCE_HEALTHY_RECOVERED")
    assert unblock_ok is True

    # Now with healthy resources, dispatch succeeds and moves file
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run, \
         mock.patch("scripts.intake_dispatcher.resolve_execution_ref", return_value="run-777"), \
         mock.patch("scripts.intake_dispatcher.time.sleep"):
        mock_run.return_value = mock.Mock(returncode=0, stdout="[]", stderr="")
        queue_processor.process_queue()

    assert not task_file.exists()
    assert (processed_dir / "job_resumed.json").exists()
    final_state = load_central_state("central_state.json")
    assert final_state["tasks"][task_id]["admission"] == ADMISSION_ADMITTED
    assert final_state["tasks"][task_id]["execution_ref"] == "run-777"
