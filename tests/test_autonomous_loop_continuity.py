import json
import os
import sys
import uuid
from pathlib import Path
from unittest import mock
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.run_autonomous_loop import AutonomousLevel6Loop
from scripts.google_builder_worker import DEFAULT_WORKER_ID
from scripts.host_guardian import AdmissionState, HostGuardian


@pytest.fixture
def repo_dir(tmp_path):
    (tmp_path / "events" / "locks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "policies").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "processed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "approvals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "chief-decisions").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "dispatch").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "agent-states").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def protect_against_host_swap_pressure():
    """Protects unit tests from live macOS background swap fluctuations."""
    with mock.patch.object(HostGuardian, "evaluate_admission", return_value=AdmissionState.OPEN):
        yield


def test_durable_workflow_state_persisted_at_each_step(repo_dir):
    """Verifies that workflow progress is durably saved to events/workflows/{workflow_id}-state.json."""
    loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=5)
    wf_id = f"wf-test-state-{uuid.uuid4().hex[:6]}"

    plan = [
        {"task_id": f"{wf_id}-s1", "instruction": "Step 1 work", "target_agent": "antigravity"},
        {"task_id": f"{wf_id}-s2", "instruction": "Step 2 work", "target_agent": "antigravity"},
    ]

    result = loop.run_multi_round_workflow(wf_id, plan)
    assert result["status"] == "COMPLETED"
    assert result["rounds_completed"] == 2

    # Check durable state file
    state_file = repo_dir / "events" / "workflows" / f"{wf_id}-state.json"
    assert state_file.exists()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["workflow_id"] == wf_id
    assert state["status"] == "COMPLETED"
    assert state["current_step_index"] == 2
    assert len(state["history"]) == 2
    assert state["history"][0]["task_id"] == f"{wf_id}-s1"
    assert state["history"][1]["task_id"] == f"{wf_id}-s2"
    assert state["history"][0]["verdict"] in ("PASS", "ACCEPTED")
    assert state["history"][1]["verdict"] in ("PASS", "ACCEPTED")


def test_unattended_resume_after_simulated_crash(repo_dir):
    """Simulates process crash/IDE exit after Step 1 and verifies unattended resumption from disk."""
    wf_id = f"wf-crash-{uuid.uuid4().hex[:6]}"
    plan = [
        {"task_id": f"{wf_id}-step-1", "instruction": "Initial step", "target_agent": "antigravity"},
        {"task_id": f"{wf_id}-step-2", "instruction": "Resumed step", "target_agent": "antigravity"},
    ]

    # Run only step 1 by capping max_iterations=1 to simulate exit after 1 step
    loop1 = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=1)
    res1 = loop1.run_multi_round_workflow(wf_id, plan)
    assert res1["status"] == "MAX_ITERATIONS_REACHED"
    assert res1["rounds_completed"] == 1

    # Verify Step 1 decision and result exist on disk
    dec1_file = repo_dir / "events" / "chief-decisions" / f"{wf_id}-step-1-chief-decision.json"
    assert dec1_file.exists()

    # Verify state shows 1 completed round
    state1 = loop1.load_workflow_state(wf_id)
    assert state1 is not None
    assert state1["current_step_index"] == 1
    assert len(state1["history"]) == 1

    # Now simulate unattended recovery via resume_interrupted_workflow in a new session
    loop2 = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=5)
    res2 = loop2.resume_interrupted_workflow(wf_id)

    assert res2["status"] == "COMPLETED"
    assert res2["rounds_completed"] == 2

    # Check that Step 2 completed and state reflects all 2 steps
    dec2_file = repo_dir / "events" / "chief-decisions" / f"{wf_id}-step-2-chief-decision.json"
    assert dec2_file.exists()

    final_state = loop2.load_workflow_state(wf_id)
    assert final_state["status"] == "COMPLETED"
    assert final_state["current_step_index"] == 2
    assert len(final_state["history"]) == 2
    assert final_state["history"][0]["task_id"] == f"{wf_id}-step-1"
    assert final_state["history"][1]["task_id"] == f"{wf_id}-step-2"


def test_provider_quota_pause_and_clean_resumption(repo_dir):
    """Verifies that provider quota limit pauses safely and resumes cleanly when limits reset."""
    loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=5)
    wf_id = f"wf-quota-{uuid.uuid4().hex[:6]}"

    # Step 1 simulates quota exhaustion via payload_override
    plan = [
        {
            "task_id": f"{wf_id}-step-1",
            "instruction": "Expensive LLM step",
            "target_agent": "antigravity",
            "payload_override": {
                "verdict": "PAUSED_PROVIDER_LIMIT",
                "error": "RESOURCE_EXHAUSTED: 429 RateLimit/Quota exceeded",
            },
        },
        {
            "task_id": f"{wf_id}-step-2",
            "instruction": "Subsequent step",
            "target_agent": "antigravity",
        },
    ]

    res = loop.run_multi_round_workflow(wf_id, plan)
    assert res["status"] == "PAUSED_PROVIDER_LIMIT"
    assert "rate/quota limit reached" in res["stop_reason"].lower()

    # Durable state must reflect PAUSED_PROVIDER_LIMIT without lost progress
    state = loop.load_workflow_state(wf_id)
    assert state is not None
    assert state["status"] == "PAUSED_PROVIDER_LIMIT"

    # Now quota restores: remove payload_override from step 1
    state["workflow_plan"][0].pop("payload_override", None)
    loop.save_workflow_state(wf_id, state)

    # Resume workflow unattended
    res_resumed = loop.resume_interrupted_workflow(wf_id)
    assert res_resumed["status"] == "COMPLETED"
    assert res_resumed["rounds_completed"] >= 2

    final_state = loop.load_workflow_state(wf_id)
    assert final_state["status"] == "COMPLETED"


def test_resource_pause_and_unattended_resume(repo_dir):
    """Verifies that HostGuardian RESOURCE_PAUSE hibernates and resumes cleanly when host recovers."""
    loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=5)
    wf_id = f"wf-host-pause-{uuid.uuid4().hex[:6]}"

    plan = [
        {"task_id": f"{wf_id}-s1", "instruction": "Step 1", "target_agent": "antigravity"},
        {"task_id": f"{wf_id}-s2", "instruction": "Step 2", "target_agent": "antigravity"},
    ]

    # Force host admission CLOSED on first attempt
    with mock.patch.object(HostGuardian, "evaluate_admission", return_value=AdmissionState.CLOSED):
        res = loop.run_multi_round_workflow(wf_id, plan)
        assert res["status"] == "RESOURCE_PAUSE"
        assert "Host admission is CLOSED" in res["stop_reason"]

    # Durable state must reflect RESOURCE_PAUSE
    state = loop.load_workflow_state(wf_id)
    assert state is not None
    assert state["status"] == "RESOURCE_PAUSE"
    assert state["current_step_index"] == 0

    # Host pressure subsides (default fixture returns OPEN)
    res_resumed = loop.resume_interrupted_workflow(wf_id)
    assert res_resumed["status"] == "COMPLETED"
    assert res_resumed["rounds_completed"] == 2

    final_state = loop.load_workflow_state(wf_id)
    assert final_state["status"] == "COMPLETED"


def test_auto_resume_pending_workflows_unattended(repo_dir):
    """Verifies that auto_resume_pending_workflows discovers and resumes all paused/interrupted workflows."""
    loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=5)
    wf1 = f"wf-pending-1-{uuid.uuid4().hex[:6]}"
    wf2 = f"wf-pending-2-{uuid.uuid4().hex[:6]}"

    # Stage workflow 1: paused on provider limit
    state1 = {
        "workflow_id": wf1,
        "correlation_id": f"corr-{wf1}",
        "workflow_plan": [
            {"task_id": f"{wf1}-s1", "instruction": "Task 1", "target_agent": "antigravity"}
        ],
        "current_step_index": 0,
        "status": "PAUSED_PROVIDER_LIMIT",
        "stop_reason": "429 Quota Exceeded",
        "history": [],
    }
    loop.save_workflow_state(wf1, state1)

    # Stage workflow 2: interrupted (status RUNNING from crashed session)
    state2 = {
        "workflow_id": wf2,
        "correlation_id": f"corr-{wf2}",
        "workflow_plan": [
            {"task_id": f"{wf2}-s1", "instruction": "Task 2", "target_agent": "antigravity"}
        ],
        "current_step_index": 0,
        "status": "RUNNING",
        "stop_reason": "IN_PROGRESS",
        "history": [],
    }
    loop.save_workflow_state(wf2, state2)

    # Auto-resume both
    results = loop.auto_resume_pending_workflows()
    assert len(results) == 2
    assert any(r["workflow_id"] == wf1 and r["status"] == "COMPLETED" for r in results)
    assert any(r["workflow_id"] == wf2 and r["status"] == "COMPLETED" for r in results)

    # Both states are now completed
    assert loop.load_workflow_state(wf1)["status"] == "COMPLETED"
    assert loop.load_workflow_state(wf2)["status"] == "COMPLETED"


def test_google_builder_worker_integration_in_autonomous_loop(repo_dir, monkeypatch):
    """Verifies that steps targeting 'google-mac' / 'builder' execute through google_builder_worker."""
    # Deterministic host sample; real overload refusal is covered in
    # tests/test_google_builder_real_execution.py.
    calm = lambda: {"memory_percent": 40.0, "swap_percent": 10.0}
    try:
        import google_builder_worker
        monkeypatch.setattr(google_builder_worker, "sample_host_capacity", calm)
    except ImportError:
        pass
    try:
        import scripts.google_builder_worker
        monkeypatch.setattr(scripts.google_builder_worker, "sample_host_capacity", calm)
    except ImportError:
        pass
    loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=3)
    wf_id = f"wf-google-builder-{uuid.uuid4().hex[:6]}"

    # Fixture file for file verification test
    fixture_file = repo_dir / "target_fixture.txt"
    fixture_file.write_text("Durable test fixture content", encoding="utf-8")

    plan = [
        {
            "task_id": f"{wf_id}-step-1",
            "instruction": "Execute deterministic transformation",
            "target_agent": "google-mac",
            "parameters": {
                "task_type": "deterministic_transform",
                "input": "courier-continuity-input",
            },
        },
        {
            "task_id": f"{wf_id}-step-2",
            "instruction": "Verify file existence and sha",
            "target_agent": "builder",
            "parameters": {
                "task_type": "verify_file",
                "target_file": str(fixture_file.relative_to(repo_dir)),
            },
        },
    ]

    result = loop.run_multi_round_workflow(wf_id, plan)
    assert result["status"] == "COMPLETED"
    assert result["rounds_completed"] == 2

    # Verify evidence files exist in events/evidence
    ev1 = repo_dir / "events" / "evidence" / f"{wf_id}-step-1_evidence.json"
    ev2 = repo_dir / "events" / "evidence" / f"{wf_id}-step-2_evidence.json"
    assert ev1.exists()
    assert ev2.exists()

    ev1_data = json.loads(ev1.read_text(encoding="utf-8"))
    assert ev1_data["task_type"] == "deterministic_transform"
    assert "transformed_result" in ev1_data

    ev2_data = json.loads(ev2.read_text(encoding="utf-8"))
    assert ev2_data["task_type"] == "verify_file"
    assert ev2_data["file_path"] == "target_fixture.txt"
