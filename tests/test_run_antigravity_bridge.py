import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.run_antigravity_bridge import (
    check_secrets_in_text,
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
)

def test_check_secrets_in_text():
    assert check_secrets_in_text("No secrets here") == 0
    assert check_secrets_in_text("Here is a token: 'ghp_123456789012345678901234567890123456'") > 0
    assert check_secrets_in_text("sk-abcdefghijklmnopqrstuvwxyz12345678901234") > 0
    assert check_secrets_in_text("api_key = 'abcdef123'") > 0


def test_visual_state_tracker(tmp_path):
    tracker = AntigravityVisualStateTracker(agent_id="test-agent", repo_dir=tmp_path)
    state = tracker.update_state(
        state="RUNNING",
        task="task-123",
        progress=0.5,
        last_action="Testing",
    )
    assert state["state"] == "RUNNING"
    assert state["progress"] == 0.5
    assert state["id"] == "test-agent"
    
    saved_file = tmp_path / "events/agent-states/test-agent.json"
    assert saved_file.exists()
    saved_data = json.loads(saved_file.read_text())
    assert saved_data["state"] == "RUNNING"


def test_antigravity_hook_runner_success(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)
    
    result_file = runner.on_task_completion(
        task_id="task-456",
        correlation_id="corr-1",
        parent_id=None,
        payload={"verdict": "PASS"}
    )
    
    assert result_file.exists()
    data = json.loads(result_file.read_text())
    assert data["type"] == "RESULT"
    assert data["status"] == "COMPLETED"
    assert data["payload"]["verdict"] == "PASS"
    assert data["payload_hash"]


def test_antigravity_hook_runner_secrets_guard(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)
    
    with pytest.raises(ValueError, match="Secret detected"):
        runner.on_task_completion(
            task_id="task-789",
            correlation_id="corr-2",
            parent_id=None,
            payload={"verdict": "PASS", "data": "ghp_123456789012345678901234567890123456"}
        )


def test_execute_bridge_task(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    # Create a job file
    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-bridge",
        "instruction": "Do something generic",
        "allowed_scope": []
    }
    job_file.write_text(json.dumps(job_data))
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    
    result_file = execute_bridge_task(job_file, hooks)
    
    assert result_file.exists()
    result_data = json.loads(result_file.read_text())
    assert result_data["payload"]["verdict"] == "PASS"
    assert result_data["payload"]["action_executed"] == "EXECUTE_INSTRUCTION"


def test_execute_bridge_task_with_fixture(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(rab, "COURIER_DIR", tmp_path)
    
    # Create a fixture file
    fixture_file = tmp_path / "fixture.md"
    fixture_file.write_text("Hello fixture!")
    
    # Create a job file
    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-fixture",
        "instruction": "Read fixture",
        "allowed_scope": ["fixture.md"]
    }
    job_file.write_text(json.dumps(job_data))
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    
    result_file = execute_bridge_task(job_file, hooks)
    
    assert result_file.exists()
    result_data = json.loads(result_file.read_text())
    assert result_data["payload"]["verdict"] == "PASS"
    assert result_data["payload"]["action_executed"] == "READ_FIXTURE_AND_SUMMARIZE"
    assert "Verified readable content" in result_data["payload"]["content_summary"]


def test_run_chief_review_router(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "DECISIONS_DIR", tmp_path / "decisions")
    
    # PASS
    result_file_pass = tmp_path / "res1.json"
    result_file_pass.write_text(json.dumps({"payload": {"verdict": "PASS"}}))
    dec1 = run_chief_review_router("t1", result_file_pass)
    assert dec1["verdict"] == "ACCEPTED"
    assert dec1["action"] == "AUTO_APPROVE_SAFE_RESULT"
    
    # NEEDS_FIX
    result_file_fix = tmp_path / "res2.json"
    result_file_fix.write_text(json.dumps({"payload": {"verdict": "NEEDS_FIX"}}))
    dec2 = run_chief_review_router("t2", result_file_fix)
    assert dec2["verdict"] == "NEEDS_FIX"
    assert dec2["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    
    # OTHER -> HUMAN
    result_file_human = tmp_path / "res3.json"
    result_file_human.write_text(json.dumps({"payload": {"verdict": "MAYBE"}}))
    dec3 = run_chief_review_router("t3", result_file_human)
    assert dec3["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert dec3["action"] == "STOP_AT_HUMAN_GATE"


def test_execute_bridge_rejects_synthetic_fixture_summary_as_verified_product_pass(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(rab, "COURIER_DIR", tmp_path)
    monkeypatch.setattr(rab, "DECISIONS_DIR", tmp_path / "decisions")

    fixture_file = tmp_path / "fixture.md"
    fixture_file.write_text("Hello fixture!")

    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-gate",
        "instruction": "Verify product behavior",
        "allowed_scope": ["fixture.md"],
        "require_verified_product_pass": True,
    }
    job_file.write_text(json.dumps(job_data))

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)

    result_file = execute_bridge_task(job_file, hooks)
    result_data = json.loads(result_file.read_text())
    assert result_data["payload"]["verdict"] == "UNVERIFIED_MOCK"
    assert result_data["payload"]["verdict"] != "PASS"

    decision = run_chief_review_router("task-test-gate", result_file)
    assert decision["verdict"] == "REJECTED_UNVERIFIED"
    assert decision["action"] == "ROUTE_TO_REAL_VERIFIER"


def test_build_local_shell_task_packet_format(tmp_path):
    from scripts.run_antigravity_bridge import build_local_shell_task_packet
    from adapters.local_shell import _params

    job_file = tmp_path / "sample_job.json"
    job_file.write_text(json.dumps({"task_id": "test-1"}))

    packet = build_local_shell_task_packet(job_file, write_filename="result.json", timeout_s=45)
    assert packet["adapter"] == "local_shell"
    assert packet["effect_class"] == "idempotent"
    assert packet["lease_ttl_s"] == 60
    assert packet["max_attempts"] == 1
    assert packet["params"]["estimated_cost_eur"] == 0.0
    assert packet["params"]["cost_class"] == "included_quota"

    # Validate against local_shell adapter's strict validator
    validated = _params(packet["params"])
    assert validated["write"] == "result.json"
    assert validated["timeout_s"] == 45
    assert isinstance(validated["command"], list)
    cmd = validated["command"]
    assert len(cmd) >= 7
    assert cmd[0] == sys.executable
    assert "--job-file" in cmd
    assert str(job_file.resolve()) in cmd
    assert "--write-evidence" in cmd
    assert "result.json" in cmd


def test_local_shell_execution_writes_evidence_file(tmp_path, monkeypatch):
    from scripts.run_antigravity_bridge import build_local_shell_task_packet
    from adapters import local_shell

    fixture_file = tmp_path / "fixture.md"
    fixture_file.write_text("Local shell test fixture")

    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-ls-exec",
        "instruction": "Test local shell adapter execution",
        "allowed_scope": [str(fixture_file)],
        "require_verified_product_pass": False,
    }
    job_file.write_text(json.dumps(job_data))

    packet = build_local_shell_task_packet(job_file, write_filename="out-result.json", timeout_s=30)
    workdir = tmp_path / "sandbox"
    workdir.mkdir()

    res = local_shell.run(packet["params"], workdir=workdir)
    assert res.outcome == "success"
    assert len(res.artifacts) == 1
    assert res.artifacts[0]["path"] == "out-result.json"

    evidence_file = workdir / "out-result.json"
    assert evidence_file.exists()
    evidence_data = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert evidence_data["type"] == "RESULT"
    assert evidence_data["status"] == "COMPLETED"
    assert evidence_data["payload"]["verdict"] == "PASS"


def test_bridge_costgate_blocks_missing_or_non_finite_cost():
    from scripts.resource_policy import CostGate

    # Missing / None cost estimate fails closed with UNKNOWN_COST (GW-13 / GW-14)
    res_none = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=None)
    assert res_none["allowed"] is False
    assert res_none["reason"] == "UNKNOWN_COST"
    assert res_none["requires_human_gate"] is True

    # NaN / Inf cost estimate fails closed with UNKNOWN_COST
    res_nan = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("nan"))
    assert res_nan["allowed"] is False
    assert res_nan["reason"] == "UNKNOWN_COST"

    res_inf = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=float("inf"))
    assert res_inf["allowed"] is False
    assert res_inf["reason"] == "UNKNOWN_COST"

    res_huge = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=10**400)
    assert res_huge["allowed"] is False
    assert res_huge["reason"] == "UNKNOWN_COST"

    # String representation is not parsed as float or zero
    res_str = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur="0.0")  # type: ignore[arg-type]
    assert res_str["allowed"] is False
    assert res_str["reason"] == "UNKNOWN_COST"

    # Bool trap (False is not treated as 0.0 EUR)
    res_bool = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=False)  # type: ignore[arg-type]
    assert res_bool["allowed"] is False
    assert res_bool["reason"] == "UNKNOWN_COST"


def test_bridge_costgate_blocks_positive_spend_without_approval():
    from scripts.resource_policy import CostGate

    # Any positive spend request is blocked without human gate
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.01)
    assert res["allowed"] is False
    assert res["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert res["requires_human_gate"] is True


def test_bridge_packet_cost_declaration_passes_gate(tmp_path):
    from scripts.run_antigravity_bridge import build_local_shell_task_packet
    from scripts.resource_policy import CostGate

    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps({"task_id": "test-cost-pass"}))

    packet = build_local_shell_task_packet(job_file)
    estimated_cost = packet["params"].get("estimated_cost_eur")
    assert estimated_cost == 0.0

    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=estimated_cost)
    assert res["allowed"] is True




